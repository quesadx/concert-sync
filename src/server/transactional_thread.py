import json
import threading
from collections import defaultdict

from src.utils.config import RESERVATION_TTL, SECTION_CONFIG
from src.utils.enums import ReservationStatus, Section, SeatState
from src.utils.protocol_validator import (
    validate_request,
    validate_reserve_payload,
    validate_reserve_batch_payload,
    validate_confirm_payload,
    validate_cancel_payload,
    ErrorCode,
)
from src.utils.error_responses import (
    build_success_response,
    build_failure_response,
    build_error_response,
    error_invalid_section,
    error_seat_out_of_bounds,
    failure_seat_not_available,
    failure_no_capacity,
    failure_transaction_not_found,
    failure_transaction_not_active,
    error_invalid_action,
    error_internal,
)


class TransactionalThread(threading.Thread):
    def __init__(self, server, client_socket, addr):
        super().__init__()
        self.server = server
        self.client_socket = client_socket
        self.addr = addr

    def run(self):
        try:
            data = self.client_socket.recv(4096)
            
            # Validate request using protocol validator
            is_valid, error_msg, request = validate_request(data)
            if not is_valid:
                response = build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)
                self.client_socket.send(json.dumps(response).encode())
                return

            action = request.get("action")

            if action == "RESERVE":
                response = self.handle_reserve(request)
            elif action == "RESERVE_BATCH":
                response = self.handle_reserve_batch(request)
            elif action == "CONFIRM":
                response = self.handle_confirm(request)
            elif action == "CANCEL":
                response = self.handle_cancel(request)
            elif action == "QUERY":
                response = self.handle_query(request)
            elif action == "QUERY_SEAT_MAP":
                response = self.handle_query_seat_map(request)
            else:
                response = error_invalid_action(action)

            self.client_socket.send(json.dumps(response).encode())
        except Exception as e:
            self.server.global_log.append("ERROR", f"Request handling failed: {str(e)}")
            error_response = error_internal(str(e))
            try:
                self.client_socket.send(json.dumps(error_response).encode())
            except Exception:
                pass  # Socket already closed or unreachable
        finally:
            try:
                self.client_socket.close()
            except Exception:
                pass

    def _group_reservation_seats_by_section(self, reservation):
        """
        Return seats grouped by section for both legacy and batch tuple formats.

        Legacy seat tuple format: (row, col)
        Batch seat tuple format: (section, row, col)
        """
        seats_by_section = {}

        for seat_info in reservation.seats:
            if len(seat_info) == 3:
                section, row, col = seat_info
            else:
                section = reservation.section
                row, col = seat_info

            if section not in seats_by_section:
                seats_by_section[section] = []
            seats_by_section[section].append((row, col))

        return seats_by_section

    def _ordered_sections(self, sections):
        section_set = set(sections)
        return [section for section in Section if section in section_set]


    def handle_reserve(self, request):
        # Validate RESERVE-specific payload
        is_valid, error_msg = validate_reserve_payload(request)
        if not is_valid:
            return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

        try:
            user_id = request["user_id"]
            section_str = request["section"]
            row = int(request["row"])
            col = int(request["col"])
            semaphore_acquired = False
            
            # Get section enum
            try:
                section = Section[section_str]
            except KeyError:
                return error_invalid_section(section_str)
            
            # Validate coordinates are within bounds (double-check; validator should catch this)
            config = SECTION_CONFIG.get(section, {})
            max_rows = config.get("rows", 0)
            max_cols = config.get("cols", 0)
            
            if row >= max_rows or col >= max_cols:
                return error_seat_out_of_bounds(section_str, row, col, max_rows, max_cols)

            session = self.server.session_manager.get_or_create(user_id)

            with self.server.mutex_manager.table_and_sections([section]):
                seats = self.server.seat_matrix.seats[section]

                # Validate seat state
                if seats[row][col] != SeatState.AVAILABLE:
                    return failure_seat_not_available(
                        section_str, row, col, seats[row][col].value
                    )

                seats[row][col] = SeatState.RESERVED

                # Try to acquire semaphore slot
                semaphore_acquired = self.server.semaphore_mgr.acquire(section, blocking=False)
                if not semaphore_acquired:
                    # Rollback: release the seat
                    seats[row][col] = SeatState.AVAILABLE
                    return failure_no_capacity(section_str)

                # Add seat to session and reset TTL
                session.seats.append((section, row, col))
                session.reset_ttl()

            session_id = session.session_id
            self.server.global_log.append(
                "RESERVE",
                f"Session:{session_id} Section:{section.name} Seat:[{row},{col}]",
            )

            return build_success_response(transaction_id=session_id, ttl=RESERVATION_TTL)

        except Exception as e:
            # Attempt rollback if something went wrong
            try:
                section = Section[request["section"]]
                row = int(request["row"])
                col = int(request["col"])
                
                with self.server.mutex_manager.sections([section]):
                    seats = self.server.seat_matrix.seats[section]
                    valid_indices = (
                        0 <= row < len(seats) and 0 <= col < len(seats[row])
                    )
                    if valid_indices and seats[row][col] == SeatState.RESERVED:
                        seats[row][col] = SeatState.AVAILABLE
                        if semaphore_acquired:
                            self.server.semaphore_mgr.release(section)
            except Exception as rollback_error:
                self.server.global_log.append("ERROR", f"Rollback failed: {str(rollback_error)}")

            self.server.global_log.append("ERROR", f"RESERVE TX failed: {str(e)}")
            return error_internal(str(e))


    def handle_reserve_batch(self, request):
        """
        Reserve multiple seats atomically. Acquires all section locks in hierarchy order,
        validates all seats, marks them as RESERVED, and acquires semaphore slots.
        
        If any seat is unavailable or semaphore acquisition fails for any section,
        rolls back ALL changes (no partial reserves).
        """
        # Validate RESERVE_BATCH-specific payload
        is_valid, error_msg = validate_reserve_batch_payload(request)
        if not is_valid:
            return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

        try:
            seats_to_reserve = request.get("seats", [])
            
            # Parse and group seats by section
            sections_and_seats = {}  # section -> [(row, col), ...]
            seat_objects = []  # original seat objects for response
            
            for seat_obj in seats_to_reserve:
                section_str = seat_obj["section"]
                row = int(seat_obj["row"])
                col = int(seat_obj["col"])
                
                try:
                    section = Section[section_str]
                except KeyError:
                    return error_invalid_section(section_str)
                
                # Validate bounds (double-check; validator should catch)
                config = SECTION_CONFIG.get(section, {})
                max_rows = config.get("rows", 0)
                max_cols = config.get("cols", 0)
                
                if row >= max_rows or col >= max_cols:
                    return error_seat_out_of_bounds(section_str, row, col, max_rows, max_cols)
                
                if section not in sections_and_seats:
                    sections_and_seats[section] = []
                
                sections_and_seats[section].append((row, col))
                seat_objects.append({"section": section_str, "row": row, "col": col})

            ordered_sections = self._ordered_sections(sections_and_seats.keys())
            reserved_seats = []  # [(section, row, col), ...]
            acquired_semaphores = defaultdict(int)

            with self.server.mutex_manager.table_and_sections(ordered_sections):
                # Validate seat availability first (no state changes yet)
                for section in ordered_sections:
                    for row, col in sections_and_seats[section]:
                        current_state = self.server.seat_matrix.seats[section][row][col]
                        if current_state != SeatState.AVAILABLE:
                            return failure_seat_not_available(
                                section.name,
                                row,
                                col,
                                current_state.value,
                            )

                # Mark seats as RESERVED
                for section in ordered_sections:
                    for row, col in sections_and_seats[section]:
                        self.server.seat_matrix.seats[section][row][col] = SeatState.RESERVED
                        reserved_seats.append((section, row, col))

                # Acquire all required semaphore slots
                for section in ordered_sections:
                    requested_count = len(sections_and_seats[section])

                    for _ in range(requested_count):
                        acquired = self.server.semaphore_mgr.acquire(section, blocking=False)
                        if not acquired:
                            # Rollback seat states inside the same critical section
                            for r_section, r_row, r_col in reserved_seats:
                                self.server.seat_matrix.seats[r_section][r_row][r_col] = SeatState.AVAILABLE

                            # Rollback acquired semaphore slots
                            for rollback_section, rollback_count in acquired_semaphores.items():
                                if rollback_count > 0:
                                    self.server.semaphore_mgr.release_multiple(rollback_section, rollback_count)

                            return failure_no_capacity(section.name)

                        acquired_semaphores[section] += 1

                # All validations passed, semaphores acquired: create transaction
                # Flatten list of seats for transaction table
                # For batch reserves spanning multiple sections, store as tuples (section, row, col)
                # For single-section batches, store as tuples too for consistency
                all_seats = []
                for section in ordered_sections:
                    for row, col in sections_and_seats[section]:
                        all_seats.append((section, row, col))

                # Create reservation transaction with all seats (as section-aware tuples)
                primary_section = list(sections_and_seats.keys())[0] if len(sections_and_seats) == 1 else Section.VIP
                try:
                    tx_id = self.server.reservation_table.add_reservation(
                        primary_section,
                        all_seats,
                        locked=True,
                    )
                except Exception:
                    # Reservation table write failed: rollback seat states and semaphores.
                    for section, row, col in reserved_seats:
                        if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                            self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE

                    for section, count in acquired_semaphores.items():
                        if count > 0:
                            self.server.semaphore_mgr.release_multiple(section, count)

                    raise

            
            self.server.global_log.append(
                "RESERVE_BATCH",
                f"TX:{tx_id} Seats:{seat_objects}",
            )
            
            response = build_success_response(
                transaction_id=tx_id,
                ttl=RESERVATION_TTL,
                reserved_seats=seat_objects
            )
            
            return response

        except Exception as e:
            self.server.global_log.append("ERROR", f"RESERVE_BATCH TX failed: {str(e)}")
            return error_internal(str(e))


    def handle_confirm(self, request):
        # Validate CONFIRM-specific payload
        is_valid, error_msg = validate_confirm_payload(request)
        if not is_valid:
            return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

        tx_id = request.get("transaction_id")

        try:
            with self.server.mutex_manager.table():
                reservation = self.server.reservation_table.reservations.get(tx_id)
                
                if not reservation:
                    return failure_transaction_not_found(tx_id)

                if reservation.state != ReservationStatus.ACTIVE:
                    return failure_transaction_not_active(tx_id, reservation.state.value)

                seats_by_section = self._group_reservation_seats_by_section(reservation)
                ordered_sections = self._ordered_sections(seats_by_section.keys())

                with self.server.mutex_manager.sections(ordered_sections):
                    # Verify all seats are RESERVED and update to SOLD
                    for section in ordered_sections:
                        for row, col in seats_by_section[section]:
                            seat_state = self.server.seat_matrix.seats[section][row][col]
                            if seat_state != SeatState.RESERVED:
                                return build_failure_response(
                                    ErrorCode.SEAT_NOT_AVAILABLE,
                                    f"Seat {section.name}({row},{col}) state is {seat_state.value}, expected RESERVED"
                                )

                            self.server.seat_matrix.seats[section][row][col] = SeatState.SOLD

                reservation.state = ReservationStatus.CONFIRMED
                cleared_reservation = self.server.reservation_table.delete_reservation(tx_id, locked=True)
                if cleared_reservation is None:
                    return error_internal(f"Reservation {tx_id} disappeared during confirm")

            self.server.global_log.append("CONFIRM", f"TX:{tx_id} confirmed")
            return build_success_response(transaction_id=tx_id)

        except Exception as e:
            self.server.global_log.append("ERROR", f"CONFIRM TX failed: {str(e)}")
            return error_internal(str(e))


    def handle_cancel(self, request):
        # Validate CANCEL-specific payload
        is_valid, error_msg = validate_cancel_payload(request)
        if not is_valid:
            return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

        tx_id = request.get("transaction_id")

        try:
            with self.server.mutex_manager.table():
                reservation = self.server.reservation_table.reservations.get(tx_id)
                
                if not reservation:
                    return failure_transaction_not_found(tx_id)

                if reservation.state != ReservationStatus.ACTIVE:
                    return failure_transaction_not_active(tx_id, reservation.state.value)

                seats_by_section = self._group_reservation_seats_by_section(reservation)
                ordered_sections = self._ordered_sections(seats_by_section.keys())
                released_counts = {section: 0 for section in ordered_sections}

                with self.server.mutex_manager.sections(ordered_sections):
                    for section in ordered_sections:
                        for row, col in seats_by_section[section]:
                            seat_state = self.server.seat_matrix.seats[section][row][col]
                            if seat_state != SeatState.RESERVED:
                                return build_failure_response(
                                    ErrorCode.SEAT_NOT_AVAILABLE,
                                    f"Seat {section.name}({row},{col}) state is {seat_state.value}, expected RESERVED"
                                )
                            self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                            released_counts[section] += 1

                reservation.state = ReservationStatus.CANCELLED
                for section, count in released_counts.items():
                    if count > 0:
                        self.server.semaphore_mgr.release_multiple(section, count)

                cleared_reservation = self.server.reservation_table.delete_reservation(tx_id, locked=True)
                if cleared_reservation is None:
                    return error_internal(f"Reservation {tx_id} disappeared during cancel")
            self.server.global_log.append(
                "CANCEL",
                f"TX:{tx_id} cancelled sections_released:{len(released_counts)}",
            )
            return build_success_response(transaction_id=tx_id)

        except Exception as e:
            self.server.global_log.append("ERROR", f"CANCEL TX failed: {str(e)}")
            return error_internal(str(e))


    def handle_query(self, request):
        """
        Query seat availability by section.
        
        Atomicity: Acquires ALL section locks in order (prevents deadlock).
        Ensures snapshot is consistent despite concurrent modifications.
        """
        try:
            sections_data = {}
            
            # Acquire ALL section locks once for a globally consistent snapshot.
            with self.server.mutex_manager.sections(list(Section)):
                for section in Section:
                    counts = self._count_section_seats(section)
                    sections_data[section.name] = counts

            return build_success_response(sections=sections_data)
        
        except Exception as e:
            self.server.global_log.append("ERROR", f"QUERY failed: {str(e)}")
            return error_internal(str(e))

    def handle_query_seat_map(self, request):
        """
        Query full seat-state matrix by section for visualization clients.

        Response shape:
        {
            "status": "SUCCESS",
            "seat_map": {
                "VIP": [["AVAILABLE", ...], ...],
                "PREFERENTIAL": [[...]],
                "GENERAL": [[...]]
            }
        }
        """
        try:
            seat_map = {}

            with self.server.mutex_manager.sections(list(Section)):
                for section in Section:
                    rows = self.server.seat_matrix.seats[section]
                    serialized_rows = []
                    for row in rows:
                        serialized_rows.append([seat.value for seat in row])
                    seat_map[section.name] = serialized_rows

            return build_success_response(seat_map=seat_map)

        except Exception as e:
            self.server.global_log.append("ERROR", f"QUERY_SEAT_MAP failed: {str(e)}")
            return error_internal(str(e))
    
    def _count_section_seats(self, section):
        """
        Count seats in section (MUST be called while section mutex is held).
        
        Returns dict with available/reserved/sold (no total, per protocol-contract-v1).
        """
        available = 0
        reserved = 0
        sold = 0
        
        for row in self.server.seat_matrix.seats[section]:
            for seat in row:
                if seat == SeatState.AVAILABLE:
                    available += 1
                elif seat == SeatState.RESERVED:
                    reserved += 1
                elif seat == SeatState.SOLD:
                    sold += 1
        
        return {
            "available": available,
            "reserved": reserved,
            "sold": sold,
        }

