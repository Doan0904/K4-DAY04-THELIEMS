"""Deterministic tests for provider retry/backoff (no network, no real sleeping).

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

from providers.openrouter_provider import OpenRouterProvider  # noqa: E402
from providers.retry import call_with_retry, retry_after_seconds, status_code  # noqa: E402


class FakeStatusError(Exception):
    def __init__(self, status: int, headers: dict[str, str] | None = None, message: str = "") -> None:
        super().__init__(message or f"HTTP {status}")
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})


class FakeGenaiError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"code {code}")
        self.code = code


def flaky(errors: list[Exception], result: str = "ok"):
    calls = {"count": 0}

    def fn() -> str:
        calls["count"] += 1
        if errors:
            raise errors.pop(0)
        return result

    return fn, calls


class CallWithRetryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sleeps: list[float] = []
        patcher = mock.patch("sys.stderr")  # keep test output clean
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_retry(self, fn, **kwargs):
        return call_with_retry(fn, sleep=self.sleeps.append, **kwargs)

    def test_retries_rate_limit_then_succeeds_with_exponential_backoff(self) -> None:
        fn, calls = flaky([FakeStatusError(429), FakeStatusError(503)])
        self.assertEqual(self.run_retry(fn, max_retries=6), "ok")
        self.assertEqual(calls["count"], 3)
        self.assertEqual(self.sleeps, [5.0, 10.0])

    def test_backoff_is_capped(self) -> None:
        fn, _ = flaky([FakeStatusError(429) for _ in range(6)])
        self.run_retry(fn, max_retries=6)
        self.assertEqual(self.sleeps, [5.0, 10.0, 20.0, 40.0, 60.0, 60.0])

    def test_gives_up_after_max_retries_and_raises_last_error(self) -> None:
        last = FakeStatusError(429)
        fn, calls = flaky([FakeStatusError(429), FakeStatusError(429), last])
        with self.assertRaises(FakeStatusError) as ctx:
            self.run_retry(fn, max_retries=2)
        self.assertIs(ctx.exception, last)
        self.assertEqual(calls["count"], 3)
        self.assertEqual(len(self.sleeps), 2)

    def test_non_retryable_status_raises_immediately(self) -> None:
        for status in (400, 401, 402, 404):
            with self.subTest(status=status):
                fn, calls = flaky([FakeStatusError(status)])
                with self.assertRaises(FakeStatusError):
                    self.run_retry(fn, max_retries=6)
                self.assertEqual(calls["count"], 1)
        self.assertEqual(self.sleeps, [])

    def test_errors_without_status_are_not_retried(self) -> None:
        fn, calls = flaky([ValueError("bad tool arguments JSON")])
        with self.assertRaises(ValueError):
            self.run_retry(fn, max_retries=6)
        self.assertEqual(calls["count"], 1)

    def test_daily_quota_is_not_retried(self) -> None:
        for message in (
            "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock more.",
            "Quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier",
        ):
            with self.subTest(message=message):
                fn, calls = flaky([FakeStatusError(429, message=message)])
                with self.assertRaises(FakeStatusError):
                    self.run_retry(fn, max_retries=6)
                self.assertEqual(calls["count"], 1)
        self.assertEqual(self.sleeps, [])

    def test_retry_after_header_is_honored_but_capped(self) -> None:
        fn, _ = flaky([FakeStatusError(429, {"retry-after": "30"}), FakeStatusError(429, {"retry-after": "600"})])
        self.run_retry(fn, max_retries=6)
        self.assertEqual(self.sleeps, [30.0, 60.0])

    def test_genai_style_code_attribute_is_retried(self) -> None:
        fn, calls = flaky([FakeGenaiError(503)])
        self.assertEqual(self.run_retry(fn, max_retries=1), "ok")
        self.assertEqual(calls["count"], 2)

    def test_env_can_disable_retries(self) -> None:
        fn, calls = flaky([FakeStatusError(429)])
        with mock.patch.dict(os.environ, {"PROVIDER_MAX_RETRIES": "0"}), self.assertRaises(FakeStatusError):
            self.run_retry(fn)
        self.assertEqual(calls["count"], 1)

    def test_helpers(self) -> None:
        self.assertEqual(status_code(FakeStatusError(429)), 429)
        self.assertIsNone(status_code(ValueError()))
        self.assertIsNone(retry_after_seconds(FakeStatusError(429, {"retry-after": "soon"})))


class OpenRouterProviderRetryTest(unittest.TestCase):
    """The OpenAI-compatible adapter (used by OpenRouter) retries the real SDK call."""

    def test_complete_retries_429_then_returns_tool_calls(self) -> None:
        message = SimpleNamespace(
            content=None,
            tool_calls=[SimpleNamespace(function=SimpleNamespace(name="clarify", arguments='{"response_type": "text"}'))],
        )
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
                mock.patch("openai.OpenAI") as client_cls, \
                mock.patch("providers.retry.time.sleep") as fake_sleep, \
                mock.patch("sys.stderr"):
            create = client_cls.return_value.chat.completions.create
            create.side_effect = [FakeStatusError(429), response]
            result = OpenRouterProvider().complete([{"role": "user", "content": "hi"}], [], tool_choice="required")
        self.assertEqual(create.call_count, 2)
        fake_sleep.assert_called_once_with(5.0)
        self.assertEqual([(c.name, c.args) for c in result.tool_calls], [("clarify", {"response_type": "text"})])

    def test_complete_does_not_retry_missing_credits(self) -> None:
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
                mock.patch("openai.OpenAI") as client_cls, \
                mock.patch("providers.retry.time.sleep") as fake_sleep:
            create = client_cls.return_value.chat.completions.create
            create.side_effect = FakeStatusError(402)
            with self.assertRaises(FakeStatusError):
                OpenRouterProvider().complete([{"role": "user", "content": "hi"}], [])
        self.assertEqual(create.call_count, 1)
        fake_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
