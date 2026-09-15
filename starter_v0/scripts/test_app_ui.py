"""Offline smoke test for the Streamlit UI (no network, no API quota).

The shared agent loop is replaced by a stub, so this checks UI wiring only:
tool calls, args, results/errors, status and artifact version are rendered, and the
turn is written to a transcript.

Run from starter_v0/:
    python -m unittest discover -s scripts -p "test_*.py" -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chat  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402


FAKE_RESULT = {
    "status": "answered",
    "assistant_text": "VPN production đang degraded (INC-1042); LT-204 không tìm thấy.",
    "rounds": [
        {
            "round": 1,
            "assistant_text": None,
            "tool_calls": [
                {"name": "check_service_status", "args": {"service": "vpn", "environment": "production"}},
                {"name": "inspect_device", "args": {"asset_id": "LT-999", "check": "vpn"}},
            ],
            "tool_results": [
                {"tool": "check_service_status", "args": {"service": "vpn", "environment": "production"},
                 "result": {"tool": "check_service_status", "status": "degraded", "incident_id": "INC-1042"}},
                {"tool": "inspect_device", "args": {"asset_id": "LT-999", "check": "vpn"},
                 "result": {"tool": "inspect_device", "asset_id": "LT-999", "error": "asset_not_found"}},
            ],
        },
        {"round": 2, "assistant_text": "VPN production đang degraded.", "tool_calls": [], "tool_results": []},
    ],
    "tool_events": [],
}


class StreamlitAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [
            mock.patch.dict(os.environ, {"HELPDESK_TRANSCRIPTS_DIR": self.tmp.name}),
            mock.patch.object(chat, "run_model_tool_loop", return_value=FAKE_RESULT),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_turn_renders_trace_and_writes_transcript(self) -> None:
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        app.run()
        self.assertFalse(app.exception, app.exception)
        self.assertTrue(any(code.value.startswith("v5+p") for code in app.code), "artifact version not shown")

        app.chat_input[0].set_value("VPN production và LT-999 lỗi").run()
        self.assertFalse(app.exception, app.exception)

        rendered = " ".join(str(item.value) for item in [*app.markdown, *app.caption])
        self.assertIn("check_service_status", rendered)
        self.assertIn("asset_not_found", rendered)
        self.assertIn("answered", rendered)
        self.assertIn("rounds: 2", rendered)
        json_blocks = [block.value for block in app.json]
        self.assertTrue(any('"LT-999"' in str(value) for value in json_blocks), "tool args not shown")

        files = list(Path(self.tmp.name).glob("*.transcript.json"))
        self.assertEqual(len(files), 1)
        transcript = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(transcript["client"], "streamlit")
        self.assertTrue(transcript["artifact_version"].startswith("v5+p"))
        self.assertEqual(transcript["turns"][0]["status"], "answered")
        self.assertEqual(transcript["turns"][0]["rounds"][0]["tool_calls"][1]["args"]["asset_id"], "LT-999")


if __name__ == "__main__":
    unittest.main()
