"""
Tests for deterministic error codes in ConcertSync protocol.

Validates that:
- Specific error conditions map to specific error_code values
- Error messages are consistent and deterministic
- Error responses follow the protocol schema
"""

import pytest

from src.utils.protocol_validator import ErrorCode
from src.utils.error_responses import (
    error_invalid_payload,
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


# ============================================================================
# ERROR RESPONSE STRUCTURE (All error types)
# ============================================================================

class TestErrorResponseStructure:
    """Verify all error responses have correct structure."""

    def test_invalid_payload_structure(self):
        """ERR_INVALID_PAYLOAD response has correct structure."""
        response = error_invalid_payload("Test message")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_PAYLOAD
        assert isinstance(response["message"], str)

    def test_invalid_section_structure(self):
        """ERR_INVALID_SECTION response has correct structure."""
        response = error_invalid_section("BALCONY")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_SECTION
        assert "BALCONY" in response["message"]

    def test_invalid_coordinates_structure(self):
        """ERR_INVALID_COORDINATES response has correct structure."""
        response = error_invalid_coordinates(-1, 5, "Row is negative")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_COORDINATES
        assert "negative" in response["message"].lower()

    def test_seat_out_of_bounds_structure(self):
        """ERR_SEAT_OUT_OF_BOUNDS response has correct structure."""
        response = error_seat_out_of_bounds("VIP", 5, 10, 5, 10)
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.SEAT_OUT_OF_BOUNDS
        assert "5" in response["message"] and "10" in response["message"]

    def test_seat_not_available_structure(self):
        """ERR_SEAT_NOT_AVAILABLE response has correct structure."""
        response = failure_seat_not_available("VIP", 5, 10, "SOLD")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.SEAT_NOT_AVAILABLE
        assert "SOLD" in response["message"]

    def test_no_capacity_structure(self):
        """ERR_NO_CAPACITY response has correct structure."""
        response = failure_no_capacity("VIP")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.NO_CAPACITY
        assert "VIP" in response["message"]

    def test_transaction_not_found_structure(self):
        """ERR_TRANSACTION_NOT_FOUND response has correct structure."""
        response = failure_transaction_not_found("tx_999")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.TRANSACTION_NOT_FOUND
        assert "tx_999" in response["message"]

    def test_transaction_not_active_structure(self):
        """ERR_TRANSACTION_NOT_ACTIVE response has correct structure."""
        response = failure_transaction_not_active("tx_123", "CONFIRMED")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.TRANSACTION_NOT_ACTIVE
        assert "CONFIRMED" in response["message"]

    def test_invalid_action_structure(self):
        """ERR_INVALID_ACTION response has correct structure."""
        response = error_invalid_action("REFUND")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_ACTION
        assert "REFUND" in response["message"]

    def test_internal_error_structure(self):
        """INTERNAL_ERROR response has correct structure."""
        response = error_internal("NoneType has no attribute 'seats'")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INTERNAL_ERROR
        assert "NoneType" in response["message"]


# ============================================================================
# ERROR CODE DETERMINISM (Same input → Same output)
# ============================================================================

class TestErrorCodeDeterminism:
    """Verify error codes are deterministic (same input → identical response)."""

    def test_error_code_determinism_seat_not_available(self):
        """Same seat/state always produces same error_code."""
        resp1 = failure_seat_not_available("VIP", 5, 10, "SOLD")
        resp2 = failure_seat_not_available("VIP", 5, 10, "SOLD")
        assert resp1["error_code"] == resp2["error_code"]
        assert resp1["error_code"] == ErrorCode.SEAT_NOT_AVAILABLE

    def test_error_code_determinism_transaction_not_found(self):
        """Same transaction_id always produces same error_code."""
        resp1 = failure_transaction_not_found("tx_123")
        resp2 = failure_transaction_not_found("tx_123")
        assert resp1["error_code"] == resp2["error_code"]
        assert resp1["error_code"] == ErrorCode.TRANSACTION_NOT_FOUND

    def test_error_code_determinism_no_capacity(self):
        """Same section always produces same error_code."""
        resp1 = failure_no_capacity("PREFERENTIAL")
        resp2 = failure_no_capacity("PREFERENTIAL")
        assert resp1["error_code"] == resp2["error_code"]
        assert resp1["error_code"] == ErrorCode.NO_CAPACITY


# ============================================================================
# STATUS CODE DIFFERENTIATION (ERROR vs FAILURE)
# ============================================================================

class TestStatusCodeDifferentiation:
    """Verify correct status code (ERROR vs FAILURE) for each situation."""

    def test_status_error_for_invalid_payload(self):
        """Invalid payload → ERROR (client fault)."""
        response = error_invalid_payload("Missing field")
        assert response["status"] == "ERROR"

    def test_status_error_for_invalid_section(self):
        """Invalid section → ERROR (client fault)."""
        response = error_invalid_section("INVALID")
        assert response["status"] == "ERROR"

    def test_status_error_for_invalid_coordinates(self):
        """Invalid coordinates → ERROR (client fault)."""
        response = error_invalid_coordinates(-1, 5, "Row is negative")
        assert response["status"] == "ERROR"

    def test_status_error_for_out_of_bounds(self):
        """Out of bounds → ERROR (client fault)."""
        response = error_seat_out_of_bounds("VIP", 100, 100, 5, 10)
        assert response["status"] == "ERROR"

    def test_status_failure_for_seat_not_available(self):
        """Seat not available → FAILURE (business logic)."""
        response = failure_seat_not_available("VIP", 5, 10, "SOLD")
        assert response["status"] == "FAILURE"

    def test_status_failure_for_no_capacity(self):
        """No capacity → FAILURE (business logic)."""
        response = failure_no_capacity("VIP")
        assert response["status"] == "FAILURE"

    def test_status_failure_for_transaction_not_found(self):
        """Transaction not found → FAILURE (business logic)."""
        response = failure_transaction_not_found("tx_999")
        assert response["status"] == "FAILURE"

    def test_status_failure_for_transaction_not_active(self):
        """Transaction not active → FAILURE (business logic)."""
        response = failure_transaction_not_active("tx_123", "CONFIRMED")
        assert response["status"] == "FAILURE"

    def test_status_error_for_internal_error(self):
        """Unexpected exception → ERROR (server fault)."""
        response = error_internal("ValueError: bad value")
        assert response["status"] == "ERROR"


# ============================================================================
# MESSAGE DETERMINISM (Consistent messaging)
# ============================================================================

class TestMessageDeterminism:
    """Verify error messages are deterministic and helpful."""

    def test_message_includes_section(self):
        """Error messages should include section when relevant."""
        response = failure_no_capacity("GENERAL")
        assert "GENERAL" in response["message"]

    def test_message_includes_transaction_id(self):
        """Error messages should include transaction_id when relevant."""
        response = failure_transaction_not_found("specific_tx_id")
        assert "specific_tx_id" in response["message"]

    def test_message_includes_seat_coordinates(self):
        """Error messages should include seat coordinates when relevant."""
        response = failure_seat_not_available("VIP", 7, 14, "RESERVED")
        assert "7" in response["message"] or "14" in response["message"]

    def test_message_non_empty(self):
        """All error messages should be non-empty."""
        assert error_invalid_payload()["message"]
        assert error_invalid_section("TEST")["message"]
        assert failure_no_capacity("VIP")["message"]
        assert failure_transaction_not_found("tx_id")["message"]
        assert error_internal("error")["message"]


# ============================================================================
# ERROR CODE ENUM VALUES
# ============================================================================

class TestErrorCodeEnumValues:
    """Verify error codes match contract specification."""

    def test_error_code_invalid_payload(self):
        """ErrorCode.INVALID_PAYLOAD matches spec."""
        assert ErrorCode.INVALID_PAYLOAD == "ERR_INVALID_PAYLOAD"

    def test_error_code_invalid_section(self):
        """ErrorCode.INVALID_SECTION matches spec."""
        assert ErrorCode.INVALID_SECTION == "ERR_INVALID_SECTION"

    def test_error_code_invalid_coordinates(self):
        """ErrorCode.INVALID_COORDINATES matches spec."""
        assert ErrorCode.INVALID_COORDINATES == "ERR_INVALID_COORDINATES"

    def test_error_code_seat_out_of_bounds(self):
        """ErrorCode.SEAT_OUT_OF_BOUNDS matches spec."""
        assert ErrorCode.SEAT_OUT_OF_BOUNDS == "ERR_SEAT_OUT_OF_BOUNDS"

    def test_error_code_seat_not_available(self):
        """ErrorCode.SEAT_NOT_AVAILABLE matches spec."""
        assert ErrorCode.SEAT_NOT_AVAILABLE == "ERR_SEAT_NOT_AVAILABLE"

    def test_error_code_no_capacity(self):
        """ErrorCode.NO_CAPACITY matches spec."""
        assert ErrorCode.NO_CAPACITY == "ERR_NO_CAPACITY"

    def test_error_code_transaction_not_found(self):
        """ErrorCode.TRANSACTION_NOT_FOUND matches spec."""
        assert ErrorCode.TRANSACTION_NOT_FOUND == "ERR_TRANSACTION_NOT_FOUND"

    def test_error_code_transaction_not_active(self):
        """ErrorCode.TRANSACTION_NOT_ACTIVE matches spec."""
        assert ErrorCode.TRANSACTION_NOT_ACTIVE == "ERR_TRANSACTION_NOT_ACTIVE"

    def test_error_code_invalid_action(self):
        """ErrorCode.INVALID_ACTION matches spec."""
        assert ErrorCode.INVALID_ACTION == "ERR_INVALID_ACTION"

    def test_error_code_internal_error(self):
        """ErrorCode.INTERNAL_ERROR matches spec."""
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"


# ============================================================================
# SCENARIO-BASED TESTS (Realistic error conditions)
# ============================================================================

class TestScenarioBasedErrors:
    """Test realistic scenarios that produce specific errors."""

    def test_scenario_reserve_invalid_section(self):
        """Scenario: Client tries to reserve in non-existent section."""
        response = error_invalid_section("EXECUTIVE")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_SECTION
        assert "EXECUTIVE" in response["message"]
        assert "Valid:" in response["message"] or "valid" in response["message"].lower()

    def test_scenario_reserve_negative_coordinates(self):
        """Scenario: Client sends negative row/col."""
        response = error_invalid_coordinates(-5, -3, "Row and col must be non-negative")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_COORDINATES
        assert "-5" in response["message"] or "-3" in response["message"]

    def test_scenario_reserve_occupied_seat(self):
        """Scenario: Reserve on seat that's already sold."""
        response = failure_seat_not_available("VIP", 2, 3, "SOLD")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.SEAT_NOT_AVAILABLE
        assert "SOLD" in response["message"]

    def test_scenario_reserve_section_full(self):
        """Scenario: Section has no available semaphore slots."""
        response = failure_no_capacity("GENERAL")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.NO_CAPACITY

    def test_scenario_confirm_expired_transaction(self):
        """Scenario: Try to confirm a transaction that expired."""
        response = failure_transaction_not_active("tx_old_12345", "EXPIRED")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.TRANSACTION_NOT_ACTIVE
        assert "EXPIRED" in response["message"]

    def test_scenario_cancel_already_cancelled(self):
        """Scenario: Try to cancel a transaction that's already cancelled."""
        response = failure_transaction_not_active("tx_cancelled_123", "CANCELLED")
        assert response["status"] == "FAILURE"
        assert response["error_code"] == ErrorCode.TRANSACTION_NOT_ACTIVE
        assert "CANCELLED" in response["message"]

    def test_scenario_malformed_json(self):
        """Scenario: Client sends malformed JSON (caught by server parser)."""
        response = error_invalid_payload("Invalid JSON: Expecting value")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INVALID_PAYLOAD

    def test_scenario_server_exception(self):
        """Scenario: Unexpected server exception during processing."""
        response = error_internal("AttributeError: 'NoneType' object has no attribute 'seats'")
        assert response["status"] == "ERROR"
        assert response["error_code"] == ErrorCode.INTERNAL_ERROR
        assert "AttributeError" in response["message"]
