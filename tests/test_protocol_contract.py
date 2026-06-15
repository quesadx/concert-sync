"""
Tests for ConcertSync JSON protocol contract (v1.0).

Validates:
- Request payload structure and validation
- Response schema compliance
- Round-trip client-server protocol adherence
"""

import json
import pytest

from src.utils.protocol_validator import (
    validate_request_json,
    validate_action,
    validate_reserve_payload,
    validate_confirm_payload,
    validate_cancel_payload,
    validate_query_payload,
    validate_request,
    validate_response,
    ErrorCode,
)


# ============================================================================
# REQUEST JSON PARSING
# ============================================================================

class TestRequestJsonParsing:
    """Test JSON parsing and basic structure validation."""

    def test_valid_json_object(self):
        """Valid JSON object should parse successfully."""
        data = '{"action": "QUERY"}'
        is_valid, msg, parsed = validate_request_json(data)
        assert is_valid is True
        assert msg is None
        assert parsed == {"action": "QUERY"}

    def test_invalid_json_syntax(self):
        """Malformed JSON should fail."""
        data = '{"action": "QUERY"'  # Missing closing brace
        is_valid, msg, parsed = validate_request_json(data)
        assert is_valid is False
        assert "Invalid JSON" in msg
        assert parsed is None

    def test_invalid_utf8(self):
        """Invalid UTF-8 bytes should fail."""
        data = b'\xff\xfe'
        is_valid, msg, parsed = validate_request_json(data)
        assert is_valid is False
        assert "UTF-8" in msg or "Unicode" in msg

    def test_json_array_rejected(self):
        """JSON array (not object) should be rejected."""
        data = '[1, 2, 3]'
        is_valid, msg, parsed = validate_request_json(data)
        assert is_valid is False
        assert "object" in msg.lower()

    def test_json_primitive_rejected(self):
        """JSON primitive (not object) should be rejected."""
        data = '"string"'
        is_valid, msg, parsed = validate_request_json(data)
        assert is_valid is False
        assert "object" in msg.lower()

    def test_bytes_input(self):
        """Bytes input should be decoded and parsed."""
        data = b'{"action": "QUERY"}'
        is_valid, msg, parsed = validate_request_json(data)
        assert is_valid is True
        assert parsed == {"action": "QUERY"}


# ============================================================================
# ACTION VALIDATION
# ============================================================================

class TestActionValidation:
    """Test action field validation."""

    def test_valid_action_reserve(self):
        """RESERVE is valid action."""
        request = {"action": "RESERVE"}
        is_valid, msg, action = validate_action(request)
        assert is_valid is True
        assert action == "RESERVE"

    def test_valid_action_confirm(self):
        """CONFIRM is valid action."""
        request = {"action": "CONFIRM"}
        is_valid, msg, action = validate_action(request)
        assert is_valid is True
        assert action == "CONFIRM"

    def test_valid_action_cancel(self):
        """CANCEL is valid action."""
        request = {"action": "CANCEL"}
        is_valid, msg, action = validate_action(request)
        assert is_valid is True
        assert action == "CANCEL"

    def test_valid_action_query(self):
        """QUERY is valid action."""
        request = {"action": "QUERY"}
        is_valid, msg, action = validate_action(request)
        assert is_valid is True
        assert action == "QUERY"

    def test_valid_action_query_seat_map(self):
        """QUERY_SEAT_MAP is valid action."""
        request = {"action": "QUERY_SEAT_MAP"}
        is_valid, msg, action = validate_action(request)
        assert is_valid is True
        assert action == "QUERY_SEAT_MAP"

    def test_missing_action(self):
        """Missing action field should fail."""
        request = {}
        is_valid, msg, action = validate_action(request)
        assert is_valid is False
        assert "action" in msg.lower()

    def test_invalid_action(self):
        """Unknown action should fail."""
        request = {"action": "REFUND"}
        is_valid, msg, action = validate_action(request)
        assert is_valid is False
        assert "REFUND" in msg or "Unknown" in msg

    def test_action_not_string(self):
        """Action must be string."""
        request = {"action": 123}
        is_valid, msg, action = validate_action(request)
        assert is_valid is False
        assert "string" in msg.lower()


# ============================================================================
# RESERVE PAYLOAD VALIDATION
# ============================================================================

class TestReservePayloadValidation:
    """Test RESERVE action payload validation."""

    def test_valid_reserve_vip(self):
        """Valid RESERVE for VIP section."""
        request = {"action": "RESERVE", "section": "VIP", "row": 2, "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is True

    def test_valid_reserve_preferential(self):
        """Valid RESERVE for PREFERENTIAL section."""
        request = {"action": "RESERVE", "section": "PREFERENTIAL", "row": 5, "col": 10}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is True

    def test_valid_reserve_general(self):
        """Valid RESERVE for GENERAL section."""
        request = {"action": "RESERVE", "section": "GENERAL", "row": 10, "col": 15}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is True

    def test_missing_section(self):
        """Missing section field should fail."""
        request = {"action": "RESERVE", "row": 2, "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "section" in msg.lower()

    def test_invalid_section(self):
        """Invalid section name should fail."""
        request = {"action": "RESERVE", "section": "BALCONY", "row": 2, "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "BALCONY" in msg

    def test_missing_row(self):
        """Missing row field should fail."""
        request = {"action": "RESERVE", "section": "VIP", "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "row" in msg.lower()

    def test_missing_col(self):
        """Missing col field should fail."""
        request = {"action": "RESERVE", "section": "VIP", "row": 2}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "col" in msg.lower()

    def test_row_not_integer(self):
        """Row must be integer."""
        request = {"action": "RESERVE", "section": "VIP", "row": "2", "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "row" in msg.lower()

    def test_col_not_integer(self):
        """Col must be integer."""
        request = {"action": "RESERVE", "section": "VIP", "row": 2, "col": "5"}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "col" in msg.lower()

    def test_row_negative(self):
        """Row cannot be negative."""
        request = {"action": "RESERVE", "section": "VIP", "row": -1, "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "non-negative" in msg.lower() or "negative" in msg.lower()

    def test_col_negative(self):
        """Col cannot be negative."""
        request = {"action": "RESERVE", "section": "VIP", "row": 2, "col": -1}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "non-negative" in msg.lower() or "negative" in msg.lower()

    def test_row_out_of_bounds_vip(self):
        """Row exceeding VIP bounds should fail."""
        # VIP config: 5 rows, 10 cols
        request = {"action": "RESERVE", "section": "VIP", "row": 5, "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "out of bounds" in msg.lower()

    def test_col_out_of_bounds_vip(self):
        """Col exceeding VIP bounds should fail."""
        request = {"action": "RESERVE", "section": "VIP", "row": 2, "col": 10}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False
        assert "out of bounds" in msg.lower()

    def test_row_boundary_vip(self):
        """Max valid row for VIP (row=4, since 0-4 for 5 rows)."""
        request = {"action": "RESERVE", "section": "VIP", "row": 4, "col": 9}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is True

    def test_section_not_string(self):
        """Section must be string."""
        request = {"action": "RESERVE", "section": 123, "row": 2, "col": 5}
        is_valid, msg = validate_reserve_payload(request)
        assert is_valid is False


# ============================================================================
# CONFIRM/CANCEL PAYLOAD VALIDATION
# ============================================================================

class TestConfirmPayloadValidation:
    """Test CONFIRM action payload validation."""

    def test_valid_confirm(self):
        """Valid CONFIRM with transaction_id."""
        request = {"action": "CONFIRM", "transaction_id": "tx_12345"}
        is_valid, msg = validate_confirm_payload(request)
        assert is_valid is True

    def test_missing_transaction_id(self):
        """Missing transaction_id should fail."""
        request = {"action": "CONFIRM"}
        is_valid, msg = validate_confirm_payload(request)
        assert is_valid is False
        assert "transaction_id" in msg.lower()

    def test_transaction_id_not_string(self):
        """transaction_id must be string."""
        request = {"action": "CONFIRM", "transaction_id": 12345}
        is_valid, msg = validate_confirm_payload(request)
        assert is_valid is False

    def test_transaction_id_empty(self):
        """transaction_id cannot be empty."""
        request = {"action": "CONFIRM", "transaction_id": ""}
        is_valid, msg = validate_confirm_payload(request)
        assert is_valid is False


class TestCancelPayloadValidation:
    """Test CANCEL action payload validation."""

    def test_valid_cancel(self):
        """Valid CANCEL with transaction_id."""
        request = {"action": "CANCEL", "transaction_id": "tx_12345"}
        is_valid, msg = validate_cancel_payload(request)
        assert is_valid is True

    def test_missing_transaction_id(self):
        """Missing transaction_id should fail."""
        request = {"action": "CANCEL"}
        is_valid, msg = validate_cancel_payload(request)
        assert is_valid is False
        assert "transaction_id" in msg.lower()


# ============================================================================
# QUERY PAYLOAD VALIDATION
# ============================================================================

class TestQueryPayloadValidation:
    """Test QUERY action payload validation."""

    def test_valid_query(self):
        """Valid QUERY (no additional fields required)."""
        request = {"action": "QUERY"}
        is_valid, msg = validate_query_payload(request)
        assert is_valid is True


# ============================================================================
# COORDINATED REQUEST VALIDATION
# ============================================================================

class TestCoordinatedRequestValidation:
    """Test master validate_request() function."""

    def test_valid_reserve_request(self):
        """Valid RESERVE request end-to-end."""
        data = '{"action": "RESERVE", "user_id": "test_user", "section": "VIP", "row": 2, "col": 5}'
        is_valid, msg, request = validate_request(data)
        assert is_valid is True
        assert request == {"action": "RESERVE", "user_id": "test_user", "section": "VIP", "row": 2, "col": 5}

    def test_invalid_json(self):
        """Invalid JSON should fail at parse step."""
        data = '{"action": "RESERVE"'
        is_valid, msg, request = validate_request(data)
        assert is_valid is False
        assert request is None

    def test_invalid_action(self):
        """Invalid action should fail at action step."""
        data = '{"action": "REFUND"}'
        is_valid, msg, request = validate_request(data)
        assert is_valid is False
        assert request is None

    def test_invalid_reserve_missing_section(self):
        """Invalid RESERVE (missing section) should fail at payload step."""
        data = '{"action": "RESERVE", "user_id": "test_user", "row": 2, "col": 5}'
        is_valid, msg, request = validate_request(data)
        assert is_valid is False
        assert request is None

    def test_valid_query_seat_map_request(self):
        """Valid QUERY_SEAT_MAP request end-to-end."""
        data = '{"action": "QUERY_SEAT_MAP"}'
        is_valid, msg, request = validate_request(data)
        assert is_valid is True
        assert request == {"action": "QUERY_SEAT_MAP"}


# ============================================================================
# RESPONSE VALIDATION
# ============================================================================

class TestResponseValidation:
    """Test response structure validation."""

    def test_valid_success_response(self):
        """Valid SUCCESS response."""
        response = {"status": "SUCCESS", "transaction_id": "tx_123", "ttl": 300}
        is_valid, msg = validate_response(response)
        assert is_valid is True

    def test_valid_failure_response(self):
        """Valid FAILURE response."""
        response = {"status": "FAILURE", "error_code": "ERR_SEAT_NOT_AVAILABLE", "message": "Seat taken"}
        is_valid, msg = validate_response(response)
        assert is_valid is True

    def test_valid_error_response(self):
        """Valid ERROR response."""
        response = {"status": "ERROR", "error_code": "ERR_INVALID_PAYLOAD", "message": "Missing field"}
        is_valid, msg = validate_response(response)
        assert is_valid is True

    def test_missing_status(self):
        """Response must have status field."""
        response = {"transaction_id": "tx_123"}
        is_valid, msg = validate_response(response)
        assert is_valid is False

    def test_invalid_status(self):
        """Status must be valid value."""
        response = {"status": "UNKNOWN"}
        is_valid, msg = validate_response(response)
        assert is_valid is False

    def test_failure_missing_error_code(self):
        """FAILURE response must have error_code."""
        response = {"status": "FAILURE", "message": "Error"}
        is_valid, msg = validate_response(response)
        assert is_valid is False

    def test_failure_missing_message(self):
        """FAILURE response must have message."""
        response = {"status": "FAILURE", "error_code": "ERR_CODE"}
        is_valid, msg = validate_response(response)
        assert is_valid is False

    def test_error_missing_error_code(self):
        """ERROR response must have error_code."""
        response = {"status": "ERROR", "message": "Error"}
        is_valid, msg = validate_response(response)
        assert is_valid is False

    def test_expected_status_match(self):
        """expected_status parameter should match."""
        response = {"status": "SUCCESS"}
        is_valid, msg = validate_response(response, expected_status="SUCCESS")
        assert is_valid is True

    def test_expected_status_mismatch(self):
        """Mismatched expected_status should fail."""
        response = {"status": "FAILURE", "error_code": "ERR", "message": "msg"}
        is_valid, msg = validate_response(response, expected_status="SUCCESS")
        assert is_valid is False
