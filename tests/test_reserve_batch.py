"""
Tests for RESERVE_BATCH feature - atomic multi-seat reservations.

Covers:
- Protocol compliance (request/response schemas)
- Atomicity guarantees (all-or-nothing)
- Edge cases (duplicates, partial failures, concurrency)
- Rollback behavior on semaphore exhaustion
"""

import pytest
import json
import time
import threading
from src.server.concert_server import ConcertServer
from src.client.concert_client import ConcertClient
from src.utils.protocol_validator import validate_request, ErrorCode


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def concert_server():
    """Start concert server for testing."""
    import os
    import socket
    
    # Remove stale SQLite DB to prevent cross-test state pollution
    try:
        os.remove("data/concert_sync.db")
    except FileNotFoundError:
        pass
    
    # Find free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
    
    server = ConcertServer(port=port)
    server.start()
    
    # Give server time to start
    time.sleep(0.5)
    
    yield type('Server', (), {'port': port, 'instance': server})()
    
    server.stop()


# ============================================================================
# PROTOCOL VALIDATION TESTS
# ============================================================================

class TestReserveBatchProtocolValidation:
    """Validate RESERVE_BATCH request schemas."""
    
    def test_valid_reserve_batch_single_seat(self):
        """Valid batch with single seat in VIP."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": [{"section": "VIP", "row": 0, "col": 0}]
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert is_valid, f"Expected valid request, got error: {msg}"
        assert parsed["action"] == "RESERVE_BATCH"
    
    def test_valid_reserve_batch_multiple_sections(self):
        """Valid batch with seats spanning VIP, PREFERENTIAL, GENERAL."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": [
                {"section": "VIP", "row": 0, "col": 0},
                {"section": "PREFERENTIAL", "row": 5, "col": 5},
                {"section": "GENERAL", "row": 10, "col": 10}
            ]
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert is_valid, f"Expected valid request, got error: {msg}"
        assert len(parsed["seats"]) == 3
    
    def test_valid_reserve_batch_max_10_seats(self):
        """Valid batch with maximum 10 seats."""
        seats = [
            {"section": "GENERAL", "row": i, "col": 0}
            for i in range(10)
        ]
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": seats
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert is_valid, f"Expected valid request, got error: {msg}"
        assert len(parsed["seats"]) == 10
    
    def test_reserve_batch_empty_seats_array(self):
        """Empty seats array should be invalid."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": []
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert not is_valid
        assert "at least 1 seat" in msg.lower()
    
    def test_reserve_batch_exceeds_max_seats(self):
        """Batch with > 10 seats should be invalid."""
        seats = [
            {"section": "GENERAL", "row": i, "col": 0}
            for i in range(11)
        ]
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": seats
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert not is_valid
        assert "at most 10" in msg.lower()
    
    def test_reserve_batch_duplicate_coordinates(self):
        """Batch with duplicate seat coordinates should be invalid."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": [
                {"section": "VIP", "row": 0, "col": 0},
                {"section": "VIP", "row": 0, "col": 0}
            ]
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert not is_valid
        assert "duplicate" in msg.lower()
    
    def test_reserve_batch_invalid_section(self):
        """Batch with invalid section should be invalid."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": [
                {"section": "BALCONY", "row": 0, "col": 0}
            ]
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert not is_valid
        assert "BALCONY" in msg
    
    def test_reserve_batch_out_of_bounds(self):
        """Batch with out-of-bounds seat should be invalid."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": [
                {"section": "VIP", "row": 100, "col": 100}
            ]
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert not is_valid
        assert "out of bounds" in msg.lower() or "out of range" in msg.lower()
    
    def test_reserve_batch_negative_coordinates(self):
        """Batch with negative coordinates should be invalid."""
        request = json.dumps({
            "action": "RESERVE_BATCH",
            "user_id": "test_user",
            "seats": [
                {"section": "VIP", "row": -1, "col": 0}
            ]
        }).encode()
        
        is_valid, msg, parsed = validate_request(request)
        assert not is_valid
        assert "negative" in msg.lower()


# ============================================================================
# ATOMICITY TESTS (Server Behavior)
# ============================================================================

class TestReserveBatchAtomicity:
    """Verify all-or-nothing semantics for batch reserves."""
    
    def test_all_seats_available_reserves_all(self, concert_server):
        """When all seats available, all should be reserved."""
        client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        seats_to_reserve = [
            {"section": "VIP", "row": 0, "col": 0},
            {"section": "VIP", "row": 0, "col": 1},
            {"section": "VIP", "row": 0, "col": 2}
        ]
        
        # RESERVE_BATCH
        response = client.send_request({
            "action": "RESERVE_BATCH",
            "seats": seats_to_reserve
        })
        
        assert response["status"] == "SUCCESS"
        assert "transaction_id" in response
        assert "reserved_seats" in response
        assert len(response["reserved_seats"]) == 3
        
        # Verify all seats are now RESERVED by trying to reserve same seats again
        for seat in seats_to_reserve:
            try:
                response = client.send_request({
                    "action": "RESERVE",
                    "section": seat["section"],
                    "row": seat["row"],
                    "col": seat["col"]
                })
                # If we get here, response should be FAILURE (in case client doesn't raise)
                assert response["status"] == "FAILURE"
                assert response["error_code"] == "ERR_SEAT_NOT_AVAILABLE"
            except Exception as e:
                # Client raises exception for FAILURE/ERROR, which is expected
                assert "ERR_SEAT_NOT_AVAILABLE" in str(e), f"Expected seat not available error, got {e}"
    
    def test_one_seat_unavailable_reserves_none(self, concert_server):
        """When any seat unavailable, no seats should be reserved."""
        client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        # Pre-occupy VIP(0,1)
        response1 = client.send_request({
            "action": "RESERVE",
            "section": "VIP",
            "row": 0,
            "col": 1
        })
        assert response1["status"] == "SUCCESS"
        tx_id_1 = response1["transaction_id"]
        
        # Confirm it
        response1_confirm = client.send_request({
            "action": "CONFIRM",
            "transaction_id": tx_id_1
        })
        assert response1_confirm["status"] == "SUCCESS"
        
        # Try RESERVE_BATCH with VIP(0,0), VIP(0,1) (unavailable), VIP(0,2)
        seats_to_reserve = [
            {"section": "VIP", "row": 0, "col": 0},
            {"section": "VIP", "row": 0, "col": 1},  # Already SOLD
            {"section": "VIP", "row": 0, "col": 2}
        ]
        
        try:
            response2 = client.send_request({
                "action": "RESERVE_BATCH",
                "seats": seats_to_reserve
            })
            assert response2["status"] == "FAILURE"
            assert response2["error_code"] == "ERR_SEAT_NOT_AVAILABLE"
        except Exception as e:
            # Client raises exception for FAILURE, which is expected
            assert "ERR_SEAT_NOT_AVAILABLE" in str(e)
        
        # Verify VIP(0,0) and VIP(0,2) were NOT reserved (still available)
        response_check_0 = client.send_request({
            "action": "RESERVE",
            "section": "VIP",
            "row": 0,
            "col": 0
        })
        assert response_check_0["status"] == "SUCCESS", "VIP(0,0) should still be available (rollback worked)"
        
        response_check_2 = client.send_request({
            "action": "RESERVE",
            "section": "VIP",
            "row": 0,
            "col": 2
        })
        assert response_check_2["status"] == "SUCCESS", "VIP(0,2) should still be available (rollback worked)"
    
    def test_batch_confirm_rolls_back_on_unavailable_middle_seat(self, concert_server):
        """Batch reserve fails if middle seat becomes unavailable just before reserve."""
        client1 = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        client2 = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        # Client2 reserves VIP(1,1)
        resp2 = client2.send_request({
            "action": "RESERVE",
            "section": "VIP",
            "row": 1,
            "col": 1
        })
        assert resp2["status"] == "SUCCESS"
        tx_2 = resp2["transaction_id"]
        
        # Client2 confirms it (now it's SOLD)
        resp2_confirm = client2.send_request({
            "action": "CONFIRM",
            "transaction_id": tx_2
        })
        assert resp2_confirm["status"] == "SUCCESS"
        
        # Client1 tries batch with VIP(1,0), VIP(1,1) (SOLD), VIP(1,2)
        try:
            resp1 = client1.send_request({
                "action": "RESERVE_BATCH",
                "seats": [
                    {"section": "VIP", "row": 1, "col": 0},
                    {"section": "VIP", "row": 1, "col": 1},  # SOLD
                    {"section": "VIP", "row": 1, "col": 2}
                ]
            })
            assert resp1["status"] == "FAILURE"
        except Exception as e:
            # Client raises exception for FAILURE, which is expected
            assert "ERR_SEAT_NOT_AVAILABLE" in str(e)
        
        # Verify rollback: VIP(1,0) and VIP(1,2) should still be AVAILABLE
        resp_check_0 = client1.send_request({
            "action": "RESERVE",
            "section": "VIP",
            "row": 1,
            "col": 0
        })
        assert resp_check_0["status"] == "SUCCESS"
        
        resp_check_2 = client1.send_request({
            "action": "RESERVE",
            "section": "VIP",
            "row": 1,
            "col": 2
        })
        assert resp_check_2["status"] == "SUCCESS"


# ============================================================================
# EDGE CASES & CONCURRENCY
# ============================================================================

class TestReserveBatchEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_batch_with_same_section_multiple_times(self, concert_server):
        """Batch with multiple seats in same section should work."""
        client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        response = client.send_request({
            "action": "RESERVE_BATCH",
            "seats": [
                {"section": "VIP", "row": 0, "col": 0},
                {"section": "VIP", "row": 0, "col": 1},
                {"section": "VIP", "row": 1, "col": 0}
            ]
        })
        
        assert response["status"] == "SUCCESS"
        assert len(response["reserved_seats"]) == 3
    
    def test_batch_ttl_field_in_response(self, concert_server):
        """Batch response should include TTL field."""
        client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        response = client.send_request({
            "action": "RESERVE_BATCH",
            "seats": [
                {"section": "GENERAL", "row": 0, "col": 0}  # GENERAL has enough rows
            ]
        })
        
        assert response["status"] == "SUCCESS"
        assert "ttl" in response
        assert isinstance(response["ttl"], int)
        assert response["ttl"] > 0
    
    def test_batch_then_confirm_all_seats(self, concert_server):
        """Can CONFIRM batch transaction to mark all seats as SOLD."""
        client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        # RESERVE_BATCH
        response = client.send_request({
            "action": "RESERVE_BATCH",
            "seats": [
                {"section": "VIP", "row": 3, "col": 3},
                {"section": "PREFERENTIAL", "row": 5, "col": 5}
            ]
        })
        
        assert response["status"] == "SUCCESS"
        tx_id = response["transaction_id"]
        
        # CONFIRM
        confirm_response = client.send_request({
            "action": "CONFIRM",
            "transaction_id": tx_id
        })
        
        assert confirm_response["status"] == "SUCCESS"
        assert confirm_response["transaction_id"] == tx_id
        
        # Verify seats are SOLD (try to reserve them again - should fail)
        for row, col, section in [(3, 3, "VIP"), (5, 5, "PREFERENTIAL")]:
            try:
                resp = client.send_request({
                    "action": "RESERVE",
                    "section": section,
                    "row": row,
                    "col": col
                })
                # If we get here without exception, response should be FAILURE
                assert resp["status"] == "FAILURE"
                assert "SOLD" in resp.get("message", "")
            except Exception as e:
                # Client raises exception for FAILURE, which is expected
                assert "SOLD" in str(e) or "ERR_SEAT_NOT_AVAILABLE" in str(e)
    
    def test_batch_then_cancel_releases_semaphore(self, concert_server):
        """CANCEL batch should release semaphore slots."""
        client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
        
        # Get initial capacity
        query1 = client.send_request({"action": "QUERY"})
        vip_available_before = query1["sections"]["VIP"]["available"]
        
        # RESERVE_BATCH (3 seats in VIP)
        response = client.send_request({
            "action": "RESERVE_BATCH",
            "seats": [
                {"section": "VIP", "row": 2, "col": 5},
                {"section": "VIP", "row": 2, "col": 6},
                {"section": "VIP", "row": 2, "col": 7}
            ]
        })
        
        assert response["status"] == "SUCCESS"
        tx_id = response["transaction_id"]
        
        # Check available decreased by 3
        query2 = client.send_request({"action": "QUERY"})
        vip_available_after_reserve = query2["sections"]["VIP"]["available"]
        assert vip_available_after_reserve == vip_available_before - 3
        
        # CANCEL
        cancel_response = client.send_request({
            "action": "CANCEL",
            "transaction_id": tx_id
        })
        assert cancel_response["status"] == "SUCCESS"
        
        # Seats should be AVAILABLE again and semaphore released
        query3 = client.send_request({"action": "QUERY"})
        vip_available_after_cancel = query3["sections"]["VIP"]["available"]
        assert vip_available_after_cancel == vip_available_before


class TestReserveBatchConcurrency:
    """Test concurrent batch and single reserves."""
    
    def test_concurrent_batch_reserves_no_double_booking(self, concert_server):
        """Multiple concurrent batch reserves should not double-book seats."""
        seats_to_reserve = [
            {"section": "GENERAL", "row": 0, "col": i}
            for i in range(10)
        ]
        
        results = {"success": [], "failure": []}
        lock = threading.Lock()
        
        def reserve_seats(client_id):
            try:
                client = ConcertClient(user_id="test_user", host='localhost', port=concert_server.port)
                response = client.send_request({
                    "action": "RESERVE_BATCH",
                    "seats": seats_to_reserve
                })
                
                with lock:
                    if response["status"] == "SUCCESS":
                        results["success"].append(client_id)
                    else:
                        results["failure"].append(client_id)
            except Exception as e:
                with lock:
                    results["failure"].append((client_id, str(e)))
        
        # 2 clients try to reserve the same 10 seats concurrently
        threads = [
            threading.Thread(target=reserve_seats, args=(i,))
            for i in range(2)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=5)
        
        # Only one should succeed
        assert len(results["success"]) == 1, "Only one batch should succeed"
        
        # Second should fail because seats taken
        assert len(results["failure"]) == 1, "Second batch should fail"
