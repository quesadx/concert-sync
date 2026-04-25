"""
Response factory for ConcertSync JSON protocol (v1.0).

Provides centralized factory functions to build valid JSON responses for:
- SUCCESS operations
- FAILURE business logic rejections
- ERROR technical problems

Ensures all responses conform to protocol-contract-v1.md schema.
"""

from typing import Dict, Any, Optional


def build_success_response(**kwargs) -> Dict[str, Any]:
    """
    Build a SUCCESS response.
    
    RESERVE:
        success_response(transaction_id="tx_123", ttl=300)
        → {"status": "SUCCESS", "transaction_id": "tx_123", "ttl": 300}
    
    CONFIRM/CANCEL:
        success_response(transaction_id="tx_123")
        → {"status": "SUCCESS", "transaction_id": "tx_123"}
    
    QUERY:
        success_response(sections={...})
        → {"status": "SUCCESS", "sections": {...}}
    
    Args:
        **kwargs: Fields to include in response (transaction_id, ttl, sections, etc.)
        
    Returns:
        Dict with status="SUCCESS" and provided fields
    """
    response = {"status": "SUCCESS"}
    response.update(kwargs)
    return response


def build_failure_response(error_code: str, message: str) -> Dict[str, Any]:
    """
    Build a FAILURE response.
    
    FAILURE indicates business logic rejected the operation (e.g., seat not available,
    transaction not found, no capacity). Client can retry with different parameters.
    
    Example:
        failure_response(
            error_code="ERR_SEAT_NOT_AVAILABLE",
            message="Seat VIP(5,10) is in SOLD state"
        )
        → {
            "status": "FAILURE",
            "error_code": "ERR_SEAT_NOT_AVAILABLE",
            "message": "Seat VIP(5,10) is in SOLD state"
        }
    
    Args:
        error_code: Deterministic error code (e.g., ERR_SEAT_NOT_AVAILABLE)
        message: Human-readable explanation
        
    Returns:
        Dict with status="FAILURE", error_code, and message
    """
    return {
        "status": "FAILURE",
        "error_code": error_code,
        "message": message
    }


def build_error_response(error_code: str, message: str) -> Dict[str, Any]:
    """
    Build an ERROR response.
    
    ERROR indicates a technical problem (invalid payload, protocol violation, 
    unexpected exception). Client cannot proceed with this request; must fix 
    payload or retry later.
    
    Example:
        error_response(
            error_code="ERR_INVALID_SECTION",
            message="Section 'BALCONY' not supported. Valid: VIP, PREFERENTIAL, GENERAL"
        )
        → {
            "status": "ERROR",
            "error_code": "ERR_INVALID_SECTION",
            "message": "Section 'BALCONY' not supported. Valid: VIP, PREFERENTIAL, GENERAL"
        }
    
    Args:
        error_code: Deterministic error code (e.g., ERR_INVALID_PAYLOAD)
        message: Human-readable explanation (often includes validation hint)
        
    Returns:
        Dict with status="ERROR", error_code, and message
    """
    return {
        "status": "ERROR",
        "error_code": error_code,
        "message": message
    }


# ============================================================================
# CONVENIENCE BUILDERS (Match common error patterns)
# ============================================================================

def error_invalid_payload(message: str = "Invalid request payload") -> Dict[str, Any]:
    """Build ERR_INVALID_PAYLOAD error response."""
    from src.utils.protocol_validator import ErrorCode
    return build_error_response(ErrorCode.INVALID_PAYLOAD, message)


def error_invalid_section(section: str) -> Dict[str, Any]:
    """Build ERR_INVALID_SECTION error response."""
    from src.utils.protocol_validator import ErrorCode
    return build_error_response(
        ErrorCode.INVALID_SECTION,
        f"Section '{section}' not supported. Valid: VIP, PREFERENTIAL, GENERAL"
    )


def error_invalid_coordinates(row: Any, col: Any, reason: str) -> Dict[str, Any]:
    """Build ERR_INVALID_COORDINATES error response."""
    from src.utils.protocol_validator import ErrorCode
    return build_error_response(
        ErrorCode.INVALID_COORDINATES,
        f"Invalid coordinates: row={row}, col={col}. Reason: {reason}"
    )


def error_seat_out_of_bounds(section: str, row: int, col: int, max_rows: int, max_cols: int) -> Dict[str, Any]:
    """Build ERR_SEAT_OUT_OF_BOUNDS error response."""
    from src.utils.protocol_validator import ErrorCode
    return build_error_response(
        ErrorCode.SEAT_OUT_OF_BOUNDS,
        f"Seat ({row}, {col}) out of bounds for {section} ({max_rows}x{max_cols})"
    )


def failure_seat_not_available(section: str, row: int, col: int, state: str) -> Dict[str, Any]:
    """Build ERR_SEAT_NOT_AVAILABLE failure response."""
    from src.utils.protocol_validator import ErrorCode
    return build_failure_response(
        ErrorCode.SEAT_NOT_AVAILABLE,
        f"Seat {section}({row},{col}) is in {state} state, not available for reservation"
    )


def failure_no_capacity(section: str) -> Dict[str, Any]:
    """Build ERR_NO_CAPACITY failure response."""
    from src.utils.protocol_validator import ErrorCode
    return build_failure_response(
        ErrorCode.NO_CAPACITY,
        f"No reservation capacity available in {section} section"
    )


def failure_transaction_not_found(tx_id: str) -> Dict[str, Any]:
    """Build ERR_TRANSACTION_NOT_FOUND failure response."""
    from src.utils.protocol_validator import ErrorCode
    return build_failure_response(
        ErrorCode.TRANSACTION_NOT_FOUND,
        f"Transaction '{tx_id}' not found in reservation table"
    )


def failure_transaction_not_active(tx_id: str, current_status: str) -> Dict[str, Any]:
    """Build ERR_TRANSACTION_NOT_ACTIVE failure response."""
    from src.utils.protocol_validator import ErrorCode
    return build_failure_response(
        ErrorCode.TRANSACTION_NOT_ACTIVE,
        f"Transaction '{tx_id}' is {current_status}, not ACTIVE"
    )


def error_invalid_action(action: str) -> Dict[str, Any]:
    """Build ERR_INVALID_ACTION error response."""
    from src.utils.protocol_validator import ErrorCode
    return build_error_response(
        ErrorCode.INVALID_ACTION,
        f"Unknown action: {action}. Valid: RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP"
    )


def error_internal(exception_msg: str) -> Dict[str, Any]:
    """Build INTERNAL_ERROR response for unexpected exceptions."""
    from src.utils.protocol_validator import ErrorCode
    return build_error_response(
        ErrorCode.INTERNAL_ERROR,
        f"Unexpected server error: {exception_msg}"
    )
