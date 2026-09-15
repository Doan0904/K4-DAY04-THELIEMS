"""Deterministic smoke tests for the team bonus tools (no network, no real data writes).

lookup_ticket_status and update_ticket are pointed at a temporary copy of the ticket
fixture and a temporary local ticket store.

Run from starter_v0/:
    python -m unittest discover -s scripts -p "test_*.py" -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import TOOL_FUNCTIONS  # noqa: E402
from tools.lookup_ticket_status import tool as lookup_module  # noqa: E402
from tools.update_ticket import tool as update_module  # noqa: E402


class BonusTicketToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fixture = Path(tmp.name) / "tickets.json"
        shutil.copy(ROOT / "helpdesk_data" / "tickets.json", self.fixture)
        self.store = Path(tmp.name) / "tickets"
        for module in (lookup_module, update_module):
            for name, value in (("TICKET_DATA_FILE", self.fixture), ("LOCAL_TICKET_DIR", self.store)):
                patcher = mock.patch.object(module, name, value)
                patcher.start()
                self.addCleanup(patcher.stop)
        self.lookup = TOOL_FUNCTIONS["lookup_ticket_status"]
        self.update = TOOL_FUNCTIONS["update_ticket"]

    def test_registered_in_registry(self) -> None:
        self.assertIs(self.lookup, lookup_module.lookup_ticket_status)
        self.assertIs(self.update, update_module.update_ticket)

    def test_lookup_existing_ticket(self) -> None:
        result = self.lookup("inc-1042")
        self.assertTrue(result["found"])
        self.assertEqual(result["ticket_id"], "INC-1042")
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["source"], "helpdesk_data")

    def test_lookup_errors(self) -> None:
        self.assertEqual(self.lookup("")["error"], "missing_ticket_id")
        self.assertEqual(self.lookup("LT-204")["error"], "invalid_ticket_id_format")
        self.assertEqual(self.lookup("INC-9999")["error"], "ticket_not_found")
        self.assertEqual(self.lookup(1042)["error"], "invalid_ticket_id_type")

    def test_update_requires_real_boolean_confirmation(self) -> None:
        for confirmed in (False, "true", 1, {"ok": True}):
            with self.subTest(confirmed=confirmed):
                result = self.update("INC-1042", priority="critical", confirmed=confirmed)
                self.assertEqual(result["status"], "needs_confirmation")
        self.assertFalse(self.store.exists(), "no write before confirmation")

    def test_update_validation(self) -> None:
        self.assertEqual(self.update("INC-1042", confirmed=True)["error"], "no_update_fields_provided")
        self.assertEqual(self.update("INC-1042", priority="urgent", confirmed=True)["error"], "invalid_priority")
        self.assertEqual(self.update("INC-1042", status="done", confirmed=True)["error"], "invalid_status")
        self.assertEqual(self.update("INC-1042", note="password=Summer2026!", confirmed=True)["error"], "restricted_sensitive_data")
        self.assertEqual(self.update("INC-9999", status="closed", confirmed=True)["error"], "ticket_not_found")
        self.assertFalse(self.store.exists())

    def test_confirmed_update_writes_local_store_not_fixture(self) -> None:
        fixture_before = self.fixture.read_bytes()
        result = self.update("INC-1042", priority="critical", note="escalated by on-call", confirmed=True)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["before"]["priority"], "high")
        self.assertEqual(result["after"]["priority"], "critical")
        self.assertEqual(self.fixture.read_bytes(), fixture_before, "fixture must stay read-only")
        self.assertTrue((self.store / "INC-1042.json").exists())
        after = self.lookup("INC-1042")
        self.assertEqual((after["priority"], after["source"]), ("critical", "local_ticket_store"))
        self.assertIn("escalated by on-call", after["technical_notes"])

    def test_update_created_local_ticket(self) -> None:
        self.store.mkdir(parents=True)
        (self.store / "LAB-ABC12345.json").write_text(json.dumps({"ticket_id": "LAB-ABC12345", "priority": "low", "summary": "VPN"}), encoding="utf-8")
        result = self.update("LAB-ABC12345", status="closed", confirmed=True)
        self.assertEqual(result["after"]["status"], "closed")
        self.assertEqual(self.lookup("LAB-ABC12345")["status"], "closed")


if __name__ == "__main__":
    unittest.main()
