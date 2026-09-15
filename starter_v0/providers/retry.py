"""Retry transient provider failures (rate limits, overloaded upstreams) with backoff.

Only HTTP statuses that are worth retrying are retried. Anything else (bad request,
missing credits, auth) is raised immediately, and so is a daily quota error, since
waiting a minute cannot fix it. When retries are exhausted the last error is raised
unchanged, so run_eval.py still records it as provider_error.
"""
from __future__ import annotations

import os
import re
import sys
import time
from typing import Callable, TypeVar


T = TypeVar("T")

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 6
BASE_DELAY_SECONDS = 5.0
MAX_DELAY_SECONDS = 60.0
# e.g. OpenRouter "free-models-per-day", Gemini "GenerateRequestsPerDayPerProjectPerModel".
DAILY_QUOTA_PATTERN = re.compile(r"per[-_ ]?day", re.IGNORECASE)


def status_code(exc: BaseException) -> int | None:
    # openai/anthropic SDKs expose status_code; google-genai exposes code.
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def is_daily_quota(exc: BaseException) -> bool:
    return bool(DAILY_QUOTA_PATTERN.search(str(exc)))


def retry_after_seconds(exc: BaseException) -> float | None:
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get("retry-after")
        return float(value) if value is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def call_with_retry(
    fn: Callable[[], T],
    *,
    label: str = "provider",
    max_retries: int | None = None,
    base_delay: float = BASE_DELAY_SECONDS,
    max_delay: float = MAX_DELAY_SECONDS,
    sleep: Callable[[float], None] | None = None,
) -> T:
    retries = int(os.getenv("PROVIDER_MAX_RETRIES", DEFAULT_MAX_RETRIES)) if max_retries is None else max_retries
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            code = status_code(exc)
            if code not in RETRYABLE_STATUS or attempt >= retries or is_daily_quota(exc):
                raise
            delay = min(max_delay, base_delay * (2 ** attempt))
            hinted = retry_after_seconds(exc)
            if hinted is not None:
                delay = min(max_delay, max(delay, hinted))
            attempt += 1
            print(f"[retry] {label}: HTTP {code}, retry {attempt}/{retries} in {delay:.0f}s", file=sys.stderr, flush=True)
            (sleep or time.sleep)(delay)
