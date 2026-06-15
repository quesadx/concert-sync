"""
Protocol validation utilities for ConcertSync JSON protocol (v1.0).

Provides centralized validation for:
- Request payload structure and types
- Field presence and value constraints
- Response schema compliance
- Error code generation
"""

import json
from typing import Tuple, Optional, Dict, Any

from src.utils.enums import Section, SeatState, ReservationStatus
from src.utils.config import SECTION_CONFIG


# ============================================================================
# ERROR CODE CONSTANTS
# ============================================================================


class ErrorCode:
    """Deterministic error codes matching protocol-contract-v1.md"""

    INVALID_PAYLOAD = "ERR_INVALID_PAYLOAD"  # 400: Missing/unparseable
    INVALID_SECTION = "ERR_INVALID_SECTION"  # 400: Section not in enum
    INVALID_COORDINATES = "ERR_INVALID_COORDINATES"  # 400: row/col not int or negative
    SEAT_OUT_OF_BOUNDS = "ERR_SEAT_OUT_OF_BOUNDS"  # 400: row/col exceeds bounds
    SEAT_NOT_AVAILABLE = "ERR_SEAT_NOT_AVAILABLE"  # 409: Seat != AVAILABLE
    NO_CAPACITY = "ERR_NO_CAPACITY"  # 409: No semaphore slots
    TRANSACTION_NOT_FOUND = "ERR_TRANSACTION_NOT_FOUND"  # 404: tx_id not in table
    TRANSACTION_NOT_ACTIVE = "ERR_TRANSACTION_NOT_ACTIVE"  # 409: tx_id != ACTIVE
    INVALID_ACTION = "ERR_INVALID_ACTION"  # 400: Unknown action
    SUBSCRIBE_FAILED = "ERR_SUBSCRIBE_FAILED"  # 400/500: Subscribe error
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 500: Unexpected exception


# ============================================================================
# REQUEST VALIDATION
# ============================================================================


def validate_request_json(
    data: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate that raw data is valid JSON.

    Args:
        data: UTF-8 encoded string (or already decoded)

    Returns:
        (is_valid, error_message, parsed_dict)
        - is_valid: True if JSON parses successfully
        - error_message: Human-readable error if invalid
        - parsed_dict: Parsed JSON dict if valid, else None
    """
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        parsed = json.loads(data)

        if not isinstance(parsed, dict):
            return False, "Payload must be a JSON object, not array or primitive", None

        return True, None, parsed

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}", None
    except UnicodeDecodeError:
        return False, "Payload must be valid UTF-8", None
    except Exception as e:
        return False, f"JSON parse error: {str(e)}", None


def validate_action(
    request: Dict[str, Any],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate that action field exists and is recognized.

    Args:
        request: Parsed JSON dict

    Returns:
        (is_valid, error_message, action)
        - is_valid: True if action is recognized
        - error_message: Human-readable error if invalid
        - action: The action string if valid
    """
    if "action" not in request:
        return False, "Missing required field: action", None

    action = request.get("action")

    if not isinstance(action, str):
        return (
            False,
            f"Field 'action' must be string, got {type(action).__name__}",
            None,
        )

    valid_actions = {
        "RESERVE",
        "RESERVE_BATCH",
        "RESERVE_SELECTED",
        "CONFIRM",
        "CANCEL",
        "QUERY",
        "QUERY_SEAT_MAP",
        "SUBSCRIBE_NOTIFICATIONS",
    }
    if action not in valid_actions:
        return (
            False,
            f"Unknown action: {action}. Valid actions: {valid_actions}",
            action,
        )

    return True, None, action


def validate_reserve_payload(request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate RESERVE request: section, row, col fields.

    Args:
        request: Parsed JSON dict (must have action="RESERVE")

    Returns:
        (is_valid, error_message)
        - is_valid: True if all RESERVE fields valid
        - error_message: Human-readable error if invalid
    """
    # Check section
    if "section" not in request:
        return False, "RESERVE: Missing required field: section"

    section_str = request.get("section")
    if not isinstance(section_str, str):
        return (
            False,
            f"RESERVE: Field 'section' must be string, got {type(section_str).__name__}",
        )

    try:
        section = Section[section_str]
    except KeyError:
        valid_sections = [s.name for s in Section]
        return (
            False,
            f"RESERVE: Section '{section_str}' not supported. Valid: {valid_sections}",
        )

    # Check row
    if "row" not in request:
        return False, "RESERVE: Missing required field: row"

    row = request.get("row")
    if not isinstance(row, int) or isinstance(row, bool):  # bool is subclass of int
        return False, f"RESERVE: Field 'row' must be integer, got {type(row).__name__}"

    if row < 0:
        return False, f"RESERVE: Field 'row' must be non-negative, got {row}"

    # Check col
    if "col" not in request:
        return False, "RESERVE: Missing required field: col"

    col = request.get("col")
    if not isinstance(col, int) or isinstance(col, bool):
        return False, f"RESERVE: Field 'col' must be integer, got {type(col).__name__}"

    if col < 0:
        return False, f"RESERVE: Field 'col' must be non-negative, got {col}"

    # Check bounds
    config = SECTION_CONFIG.get(section, {})
    max_rows = config.get("rows", 0)
    max_cols = config.get("cols", 0)

    if row >= max_rows or col >= max_cols:
        return (
            False,
            f"RESERVE: Seat ({row}, {col}) out of bounds for {section_str} ({max_rows}x{max_cols})",
        )

    return True, None


def validate_confirm_payload(request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate CONFIRM request: transaction_id field.

    Args:
        request: Parsed JSON dict (must have action="CONFIRM")

    Returns:
        (is_valid, error_message)
    """
    if "transaction_id" not in request:
        return False, "CONFIRM: Missing required field: transaction_id"

    tx_id = request.get("transaction_id")
    if not isinstance(tx_id, str):
        return (
            False,
            f"CONFIRM: Field 'transaction_id' must be string, got {type(tx_id).__name__}",
        )

    if not tx_id.strip():
        return False, "CONFIRM: Field 'transaction_id' cannot be empty"

    return True, None


def validate_cancel_payload(request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate CANCEL request: transaction_id field.

    Args:
        request: Parsed JSON dict (must have action="CANCEL")

    Returns:
        (is_valid, error_message)
    """
    if "transaction_id" not in request:
        return False, "CANCEL: Missing required field: transaction_id"

    tx_id = request.get("transaction_id")
    if not isinstance(tx_id, str):
        return (
            False,
            f"CANCEL: Field 'transaction_id' must be string, got {type(tx_id).__name__}",
        )

    if not tx_id.strip():
        return False, "CANCEL: Field 'transaction_id' cannot be empty"

    return True, None


def validate_reserve_batch_payload(
    request: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Validate RESERVE_BATCH request: seats array with section/row/col for each.

    Args:
        request: Parsed JSON dict (must have action="RESERVE_BATCH")

    Returns:
        (is_valid, error_message)
    """
    # Check seats array
    if "seats" not in request:
        return False, "RESERVE_BATCH: Missing required field: seats"

    seats = request.get("seats")
    if not isinstance(seats, list):
        return (
            False,
            f"RESERVE_BATCH: Field 'seats' must be array, got {type(seats).__name__}",
        )

    # Batch size: at least 1, at most 10
    if len(seats) == 0:
        return False, "RESERVE_BATCH: seats array must contain at least 1 seat"

    if len(seats) > 10:
        return (
            False,
            f"RESERVE_BATCH: seats array must contain at most 10 seats, got {len(seats)}",
        )

    # Track coordinates to detect duplicates
    seen_coords = set()

    for idx, seat in enumerate(seats):
        if not isinstance(seat, dict):
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}] must be object, got {type(seat).__name__}",
            )

        # Validate section
        if "section" not in seat:
            return False, f"RESERVE_BATCH: seats[{idx}] missing required field: section"

        section_str = seat.get("section")
        if not isinstance(section_str, str):
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}].section must be string, got {type(section_str).__name__}",
            )

        try:
            section = Section[section_str]
        except KeyError:
            valid_sections = [s.name for s in Section]
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}] section '{section_str}' not supported. Valid: {valid_sections}",
            )

        # Validate row
        if "row" not in seat:
            return False, f"RESERVE_BATCH: seats[{idx}] missing required field: row"

        row = seat.get("row")
        if not isinstance(row, int) or isinstance(row, bool):
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}].row must be integer, got {type(row).__name__}",
            )

        if row < 0:
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}].row must be non-negative, got {row}",
            )

        # Validate col
        if "col" not in seat:
            return False, f"RESERVE_BATCH: seats[{idx}] missing required field: col"

        col = seat.get("col")
        if not isinstance(col, int) or isinstance(col, bool):
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}].col must be integer, got {type(col).__name__}",
            )

        if col < 0:
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}].col must be non-negative, got {col}",
            )

        # Check bounds
        config = SECTION_CONFIG.get(section, {})
        max_rows = config.get("rows", 0)
        max_cols = config.get("cols", 0)

        if row >= max_rows or col >= max_cols:
            return (
                False,
                f"RESERVE_BATCH: seats[{idx}] ({row}, {col}) out of bounds for {section_str} ({max_rows}x{max_cols})",
            )

        # Check for duplicates
        coord_key = (section_str, row, col)
        if coord_key in seen_coords:
            return (
                False,
                f"RESERVE_BATCH: Duplicate seat coordinate {section_str}({row},{col}) at index {idx}",
            )

        seen_coords.add(coord_key)

    return True, None


def validate_query_payload(request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate QUERY request (minimal: just action required).

    Args:
        request: Parsed JSON dict (must have action="QUERY")

    Returns:
        (is_valid, error_message)
    """
    # QUERY has no additional fields required beyond action
    return True, None


def validate_query_seat_map_payload(
    request: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Validate QUERY_SEAT_MAP request (minimal: just action required).

    Args:
        request: Parsed JSON dict (must have action="QUERY_SEAT_MAP")

    Returns:
        (is_valid, error_message)
    """
    # QUERY_SEAT_MAP has no additional fields required beyond action.
    return True, None


def validate_subscribe_payload(request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate SUBSCRIBE_NOTIFICATIONS request: user_id field.

    Args:
        request: Parsed JSON dict (must have action="SUBSCRIBE_NOTIFICATIONS")

    Returns:
        (is_valid, error_message)
    """
    if "user_id" not in request:
        return False, "SUBSCRIBE_NOTIFICATIONS: Missing required field: user_id"

    user_id = request.get("user_id")
    if not isinstance(user_id, str):
        return (
            False,
            f"SUBSCRIBE_NOTIFICATIONS: Field 'user_id' must be string, got {type(user_id).__name__}",
        )

    if not user_id.strip():
        return False, "SUBSCRIBE_NOTIFICATIONS: Field 'user_id' cannot be empty"

    return True, None


# ============================================================================
# COORDINATED VALIDATION FLOW
# ============================================================================


def validate_request(data: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Master validation function: parse JSON and validate action/payload.

    Returns:
        (is_valid, error_message, request_dict)
        - is_valid: True if request passes all validation
        - error_message: Reason if invalid (includes error_code hint)
        - request_dict: Parsed request if valid, else None
    """
    # Step 1: Parse JSON
    is_valid, msg, parsed = validate_request_json(data)
    if not is_valid:
        return False, msg, None

    # Step 2: Validate action exists and is recognized
    is_valid, msg, action = validate_action(parsed)
    if not is_valid:
        return False, msg, None

    # Step 2.5: Validate user_id presence (skipped for QUERY / QUERY_SEAT_MAP)
    if action not in ("QUERY", "QUERY_SEAT_MAP"):
        if "user_id" not in parsed:
            return False, "Missing required field: user_id", None
        user_id = parsed["user_id"]
        if not isinstance(user_id, str) or not user_id.strip():
            return False, "Field 'user_id' must be a non-empty string", None

    # Step 3: Validate action-specific payload
    if action == "RESERVE":
        is_valid, msg = validate_reserve_payload(parsed)
    elif action == "RESERVE_BATCH":
        is_valid, msg = validate_reserve_batch_payload(parsed)
    elif action == "RESERVE_SELECTED":
        is_valid, msg = validate_reserve_batch_payload(parsed)
    elif action == "CONFIRM":
        is_valid, msg = validate_confirm_payload(parsed)
    elif action == "CANCEL":
        is_valid, msg = validate_cancel_payload(parsed)
    elif action == "QUERY":
        is_valid, msg = validate_query_payload(parsed)
    elif action == "QUERY_SEAT_MAP":
        is_valid, msg = validate_query_seat_map_payload(parsed)
    elif action == "SUBSCRIBE_NOTIFICATIONS":
        is_valid, msg = validate_subscribe_payload(parsed)

    if not is_valid:
        return False, msg, None

    return True, None, parsed


# ============================================================================
# RESPONSE VALIDATION (Client-side)
# ============================================================================


def validate_response(
    response: Dict[str, Any], expected_status: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a response from server conforms to protocol schema.

    Args:
        response: Parsed response dict
        expected_status: If specified, check that status matches (SUCCESS, FAILURE, or ERROR)

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(response, dict):
        return False, "Response must be a JSON object"

    if "status" not in response:
        return False, "Response missing required field: status"

    status = response.get("status")
    valid_statuses = {"SUCCESS", "FAILURE", "ERROR"}

    if status not in valid_statuses:
        return False, f"Response status must be one of {valid_statuses}, got: {status}"

    if expected_status and status != expected_status:
        return False, f"Expected status {expected_status}, got {status}"

    # FAILURE and ERROR must have error_code and message
    if status in ("FAILURE", "ERROR"):
        if "error_code" not in response:
            return False, f"{status} response missing required field: error_code"
        if "message" not in response:
            return False, f"{status} response missing required field: message"

        if not isinstance(response.get("error_code"), str):
            return False, f"{status} response: error_code must be string"
        if not isinstance(response.get("message"), str):
            return False, f"{status} response: message must be string"

    # SUCCESS responses check action-specific fields
    elif status == "SUCCESS":
        # For now, we don't validate action-specific fields deeply
        # (caller knows what action was sent and can validate accordingly)
        pass

    return True, None
