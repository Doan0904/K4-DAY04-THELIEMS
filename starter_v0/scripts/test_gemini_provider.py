"""Deterministic tests for Gemini tool_choice handling (no network, no API quota).

Run from starter_v0/:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from providers.gemini_provider import GeminiProvider, _function_calling_mode  # noqa: E402


TOOLS = [{
    "type": "function",
    "function": {
        "name": "check_service_status",
        "description": "Read shared service status.",
        "parameters": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]},
    },
}]
MESSAGES = [
    {"role": "system", "content": "You are a helpdesk agent."},
    {"role": "user", "content": "Is VPN production down?"},
]


def _fake_response() -> SimpleNamespace:
    call = SimpleNamespace(name="check_service_status", args={"service": "vpn"})
    part = SimpleNamespace(text=None, function_call=call)
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))], function_calls=[])


class FunctionCallingModeTest(unittest.TestCase):
    def test_required_maps_to_any(self) -> None:
        self.assertEqual(_function_calling_mode("required"), "ANY")

    def test_auto_and_none_map_to_gemini_modes(self) -> None:
        self.assertEqual(_function_calling_mode("auto"), "AUTO")
        self.assertEqual(_function_calling_mode("none"), "NONE")

    def test_case_and_whitespace_insensitive(self) -> None:
        self.assertEqual(_function_calling_mode(" Required "), "ANY")

    def test_unset_leaves_model_default(self) -> None:
        self.assertIsNone(_function_calling_mode(None))

    def test_unsupported_value_fails_loudly(self) -> None:
        for value in ("any_tool", {"type": "any"}, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _function_calling_mode(value)


class GeminiCompleteToolChoiceTest(unittest.TestCase):
    """Check the request actually sent to the SDK, with the client mocked out."""

    def _complete(self, *, tools, tool_choice):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
                mock.patch("google.genai.Client") as client_cls:
            generate = client_cls.return_value.models.generate_content
            generate.return_value = _fake_response()
            response = GeminiProvider().complete(MESSAGES, tools, tool_choice=tool_choice)
        return response, generate.call_args.kwargs["config"]

    def test_required_sends_mode_any(self) -> None:
        response, config = self._complete(tools=TOOLS, tool_choice="required")
        self.assertIsNotNone(config.tool_config)
        self.assertEqual(config.tool_config.function_calling_config.mode.value, "ANY")
        self.assertEqual([call.name for call in response.tool_calls], ["check_service_status"])

    def test_no_tool_choice_sends_no_tool_config(self) -> None:
        _, config = self._complete(tools=TOOLS, tool_choice=None)
        self.assertIsNone(config.tool_config)
        self.assertEqual(len(config.tools), 1)

    def test_tool_choice_ignored_without_tools(self) -> None:
        # Gemini rejects tool_config when no function declarations are sent.
        _, config = self._complete(tools=[], tool_choice="required")
        self.assertIsNone(config.tool_config)
        self.assertIsNone(config.tools)

    def test_unsupported_tool_choice_raises_before_api_call(self) -> None:
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
                mock.patch("google.genai.Client") as client_cls:
            with self.assertRaises(ValueError):
                GeminiProvider().complete(MESSAGES, TOOLS, tool_choice="sometimes")
            client_cls.return_value.models.generate_content.assert_not_called()


if __name__ == "__main__":
    unittest.main()
