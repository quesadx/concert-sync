import json
import threading

from src.utils.config import RESERVATION_TTL, SECTION_CONFIG
from src.utils.enums import ReservationStatus, Section, SeatState
from src.utils.protocol_validator import (
    validate_request,
    validate_reserve_payload,
    validate_confirm_payload,
    validate_cancel_payload,
    ErrorCode,
)
from src.utils.error_responses import (
    build_success_response,
    build_failure_response,
    build_error_response,
    error_invalid_section,
    error_invalid_coordinates,
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
            elif action == "CONFIRM":
                response = self.handle_confirm(request)
            elif action == "CANCEL":
                response = self.handle_cancel(request)
            elif action == "QUERY":
                response = self.handle_query(request)
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


    def handle_reserve(self, request):
        # Validate RESERVE-specific payload
        is_valid, error_msg = validate_reserve_payload(request)
        if not is_valid:
            return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

        try:
            section_str = request["section"]
            row = int(request["row"])
            col = int(request["col"])
            
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

            with self.server.seat_matrix.mutex_sections[section]:
                seats = self.server.seat_matrix.seats[section]

                # Validate seat state
                if seats[row][col] != SeatState.AVAILABLE:
                    return failure_seat_not_available(
                        section_str, row, col, seats[row][col].value
                    )

                seats[row][col] = SeatState.RESERVED

                # Try to acquire semaphore slot
                acquired = self.server.semaphore_mgr.acquire(section, blocking=False)
                if not acquired:
                    # Rollback: release the seat
                    seats[row][col] = SeatState.AVAILABLE
                    return failure_no_capacity(section_str)

            # Create reservation transaction
            tx_id = self.server.reservation_table.add_reservation(section, [(row, col)])

            self.server.global_log.append(
                "RESERVE",
                f"TX:{tx_id} Section:{section.name} Seat:[{row},{col}]",
            )

            return build_success_response(transaction_id=tx_id, ttl=RESERVATION_TTL)

        except Exception as e:
            # Attempt rollback if something went wrong
            try:
                section = Section[request["section"]]
                row = int(request["row"])
                col = int(request["col"])
                
                with self.server.seat_matrix.mutex_sections[section]:
                    seats = self.server.seat_matrix.seats[section]
                    valid_indices = (
                        0 <= row < len(seats) and 0 <= col < len(seats[row])
                    )
                    if valid_indices and seats[row][col] == SeatState.RESERVED:
                        seats[row][col] = SeatState.AVAILABLE
                        self.server.semaphore_mgr.release(section)
            except Exception as rollback_error:
                self.server.global_log.append("ERROR", f"Rollback failed: {str(rollback_error)}")

            self.server.global_log.append("ERROR", f"RESERVE TX failed: {str(e)}")
            return error_internal(str(e))


    def handle_confirm(self, request):
        # Validate CONFIRM-specific payload
        is_valid, error_msg = validate_confirm_payload(request)
        if not is_valid:
            return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

        tx_id = request.get("transaction_id")

        try:
            with self.server.reservation_table.mutex_table:
                reservation = self.server.reservation_table.reservations.get(tx_id)
                
                if not reservation:
                    return failure_transaction_not_found(tx_id)
                
                if reservation.state != ReservationStatus.ACTIVE:
                    return failure_transaction_not_active(tx_id, reservation.state.value)

                section = reservation.section
                
                with self.server.seat_matrix.mutex_sections[section]:
                    for row, col in reservation.seats:
                        seat_state = self.server.seat_matrix.seats[section][row][col]
                        if seat_state != SeatState.RESERVED:
                            return build_failure_response(
                                ErrorCode.SEAT_NOT_AVAILABLE,
                                f"Seat {section.name}({row},{col}) state is {seat_state.value}, expected RESERVED"
                            )

                        self.server.seat_matrix.seats[section][row][col] = SeatState.SOLD

                reservation.state = ReservationStatus.CONFIRMED

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
            with self.server.reservation_table.mutex_table:
                reservation = self.server.reservation_table.reservations.get(tx_id)
                
                if not reservation:
                    return failure_transaction_not_found(tx_id)
                
                if reservation.state != ReservationStatus.ACTIVE:
                    return failure_transaction_not_active(tx_id, reservation.state.value)

                section = reservation.section
                released_count = 0

                with self.server.seat_matrix.mutex_sections[section]:
                    for row, col in reservation.seats:
                        if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                            self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                            released_count += 1

                reservation.state = ReservationStatus.CANCELLED
                self.server.semaphore_mgr.release_multiple(section, released_count)

            self.server.global_log.append(
                "CANCEL",
                f"TX:{tx_id} cancelled seats_released:{released_count}",
            )
            return build_success_response(transaction_id=tx_id)

        except Exception as e:
            self.server.global_log.append("ERROR", f"CANCEL TX failed: {str(e)}")
            return error_internal(str(e))


    def handle_query(self, request):
        try:
            sections_data = {}
            for section in Section:
                sections_data[section.name] = self.server.seat_matrix.get_section_counts(section)

            return build_success_response(sections=sections_data)
        
        except Exception as e:
            self.server.global_log.append("ERROR", f"QUERY failed: {str(e)}")
            return error_internal(str(e))
