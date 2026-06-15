"""
Ticket generation tests for ConcertSync.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from src.utils.ticket_generator import TicketGenerator


class FakeLog:
    def __init__(self):
        self.entries = []

    def append(self, *args):
        self.entries.append(args)


class TestTicketGenerator:
    def setup_method(self):
        self.log = FakeLog()
        self.tg = TicketGenerator(self.log)
        # Override ticket dir to temp for tests
        self.test_dir = tempfile.mkdtemp()
        self.tg._tickets_dir = Path(self.test_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_ticket_creates_files(self):
        result = self.tg.generate_ticket(
            ticket_id="TKT-000001",
            section_name="VIP",
            seats=[(3, 0), (3, 1)],
            transaction_id="tx-test-123",
            timestamp=1718383500.0,
        )
        assert result is True
        txt_path = os.path.join(self.test_dir, "ticket_tkt-000001.txt")
        png_path = os.path.join(self.test_dir, "ticket_tkt-000001.png")
        assert os.path.exists(txt_path), "TXT file not found"
        assert os.path.exists(png_path), "PNG file not found"

    def test_ticket_txt_content(self):
        self.tg.generate_ticket(
            ticket_id="TKT-000002",
            section_name="PREFERENTIAL",
            seats=[(5, 10)],
            transaction_id="tx-456",
            timestamp=1718383500.0,
        )
        txt_path = os.path.join(self.test_dir, "ticket_tkt-000002.txt")
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "TKT-000002" in content
        assert "PREFERENTIAL" in content
        assert "CONFIRMADO" in content
        assert "tx-456" in content
        assert "F5-K" in content  # row=5, col=10 -> col letter K

    def test_ticket_qr_scannable(self):
        """Verify PNG is a valid image (QR code)."""
        self.tg.generate_ticket(
            ticket_id="TKT-000003",
            section_name="GENERAL",
            seats=[(0, 0)],
            transaction_id="tx-789",
            timestamp=1718383500.0,
        )
        png_path = os.path.join(self.test_dir, "ticket_tkt-000003.png")
        from PIL import Image
        img = Image.open(png_path)
        assert img.size[0] >= 100  # QR should be at least 100px
        assert img.size[1] >= 100

    def test_generate_ticket_failure_logged(self):
        """When ticket dir is invalid, error is logged but no exception."""
        self.tg._tickets_dir = Path("/nonexistent/path/that/cannot/be/created")
        result = self.tg.generate_ticket(
            ticket_id="TKT-000004",
            section_name="VIP",
            seats=[(0, 0)],
            transaction_id="tx-fail",
            timestamp=1718383500.0,
        )
        assert result is False  # graceful failure
        assert any("ERROR" in str(e) and "Ticket" in str(e) for e in self.log.entries)

    def test_ticket_id_format_in_filename(self):
        self.tg.generate_ticket(
            ticket_id="TKT-000100",
            section_name="VIP",
            seats=[(1, 2)],
            transaction_id="tx-100",
        )
        txt_path = os.path.join(self.test_dir, "ticket_tkt-000100.txt")
        assert os.path.exists(txt_path), f"File {txt_path} should exist"
