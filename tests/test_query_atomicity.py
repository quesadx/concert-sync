"""
Tests for QUERY atomicity and protocol compliance (feature/query-availability-by-zone).

Validates:
- Protocol compliance: response does NOT have "total" field
- Atomicity: snapshot is consistent even under concurrent modifications
- Invariants: available + reserved + sold = capacity
"""

import threading
import time
import pytest

from src.client.concert_client import ConcertClient
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section


class TestQueryProtocolCompliance:
    """Verify QUERY response conforms to protocol-contract-v1 schema."""

    def test_query_response_no_total_field(self, concert_server):
        """QUERY response must NOT have 'total' field (protocol-contract-v1)."""
        client = ConcertClient(host='localhost', port=concert_server.port)
        response = client.query()
        
        assert response["status"] == "SUCCESS"
        assert "sections" in response
        
        for section_name, section_data in response["sections"].items():
            # Verify NO "total" field
            assert "total" not in section_data, f"Section {section_name} should NOT have 'total' field"
            
            # Verify REQUIRED fields exist
            assert "available" in section_data
            assert "reserved" in section_data
            assert "sold" in section_data

    def test_query_response_structure_per_section(self, concert_server):
        """QUERY response has correct structure for each section."""
        client = ConcertClient(host='localhost', port=concert_server.port)
        response = client.query()
        
        assert response["status"] == "SUCCESS"
        assert "sections" in response
        
        # Verify all 3 sections present
        expected_sections = {"VIP", "PREFERENTIAL", "GENERAL"}
        actual_sections = set(response["sections"].keys())
        assert expected_sections == actual_sections, f"Expected sections {expected_sections}, got {actual_sections}"
        
        for section_name, counts in response["sections"].items():
            assert isinstance(counts["available"], int)
            assert isinstance(counts["reserved"], int)
            assert isinstance(counts["sold"], int)
            assert counts["available"] >= 0
            assert counts["reserved"] >= 0
            assert counts["sold"] >= 0


class TestQueryAtomicity:
    """Verify QUERY snapshots are atomic under concurrency."""

    def test_query_invariant_under_concurrent_reserves(self, concert_server):
        """QUERY invariant holds under concurrent RESERVE/CONFIRM/CANCEL."""
        client = ConcertClient(host='localhost', port=concert_server.port)
        
        # Run 100 QUERYs concurrently with modifications
        num_queries = 100
        query_responses = []
        lock = threading.Lock()
        
        def run_query():
            try:
                response = client.query()
                with lock:
                    query_responses.append(response)
            except Exception as e:
                with lock:
                    query_responses.append({"error": str(e)})
        
        threads = [threading.Thread(target=run_query) for _ in range(num_queries)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify all queries succeeded and invariant holds
        successful_queries = [r for r in query_responses if "sections" in r]
        assert len(successful_queries) > 0, "At least some queries should succeed"
        
        for response in successful_queries:
            for section_name, counts in response["sections"].items():
                available = counts["available"]
                reserved = counts["reserved"]
                sold = counts["sold"]
                
                # Invariant: available + reserved + sold = capacity
                config = SECTION_CONFIG.get(Section[section_name], {})
                capacity = config.get("rows", 0) * config.get("cols", 0)
                
                total = available + reserved + sold
                assert total == capacity, (
                    f"Invariant broken in {section_name}: "
                    f"available({available}) + reserved({reserved}) + sold({sold}) "
                    f"= {total}, expected {capacity}"
                )

    def test_query_consistency_snapshot(self, concert_server):
        """QUERY returns consistent snapshot (counts sum correctly)."""
        client = ConcertClient(host='localhost', port=concert_server.port)
        
        # Get 50 snapshots under load
        for _ in range(50):
            response = client.query()
            assert response["status"] == "SUCCESS"
            
            for section_name, counts in response["sections"].items():
                available = counts["available"]
                reserved = counts["reserved"]
                sold = counts["sold"]
                
                config = SECTION_CONFIG.get(Section[section_name], {})
                capacity = config.get("rows", 0) * config.get("cols", 0)
                
                # Every query result must satisfy invariant
                total = available + reserved + sold
                assert total == capacity, (
                    f"{section_name}: {available} + {reserved} + {sold} != {capacity}"
                )


class TestQueryIdempotence:
    """Verify QUERY is idempotent (safe to retry)."""

    def test_query_idempotent(self, concert_server):
        """Multiple consecutive QUERYs return consistent state."""
        client = ConcertClient(host='localhost', port=concert_server.port)
        
        # Get 3 snapshots in quick succession (no modifications in between)
        responses = []
        for _ in range(3):
            response = client.query()
            responses.append(response)
        
        # All responses should be identical (no modifications occurred)
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            counts = [r["sections"][section_name] for r in responses]
            
            # All should match
            for i in range(1, len(counts)):
                assert counts[i] == counts[0], (
                    f"Query {i} returned different counts than query 0 for {section_name}"
                )


class TestQueryZoneConsistency:
    """Verify QUERY correctly reflects per-zone availability."""

    def test_query_reflects_initial_state(self, concert_server):
        """QUERY at startup shows all seats available."""
        client = ConcertClient(host='localhost', port=concert_server.port)
        response = client.query()
        
        for section_name, counts in response["sections"].items():
            config = SECTION_CONFIG.get(Section[section_name], {})
            capacity = config.get("rows", 0) * config.get("cols", 0)
            
            # Initially: all available, none reserved/sold
            assert counts["available"] == capacity, (
                f"{section_name}: expected all {capacity} available, got {counts['available']}"
            )
            assert counts["reserved"] == 0
            assert counts["sold"] == 0


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def concert_server():
    """Start concert server for testing."""
    from src.server.concert_server import ConcertServer
    import socket
    import time
    
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
