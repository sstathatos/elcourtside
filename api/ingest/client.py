"""Polite HTTP client: global rate limit, retries with backoff, JSON parsing."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

USER_AGENT = "elcourtside/0.1 (fan project; st.stathatos@gmail.com)"

RETRY_STATUSES = {429, 500, 502, 503, 504}


class NotFoundError(Exception):
    """The resource does not exist (HTTP 404) — often expected, e.g. old PBP."""


class ApiError(Exception):
    """Non-retryable client error or retries exhausted."""


class PoliteClient:
    def __init__(self, min_interval: float = 2.0, timeout: float = 30.0,
                 max_attempts: int = 4, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, clock=time.monotonic):
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self.requests_made = 0
        self._sleep = sleep
        self._clock = clock
        self._next_at = clock()
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
            transport=transport,
        )

    def _pace(self) -> None:
        wait = self._next_at - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._next_at = self._clock() + self.min_interval

    def get_json(self, url: str, params: dict | None = None) -> tuple[bytes, Any]:
        """GET url and return (raw_body, parsed_json_or_None)."""
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            if attempt:
                self._sleep(2 ** attempt)  # 2s, 4s, 8s on top of pacing
            self._pace()
            try:
                resp = self._client.get(url, params=params)
                self.requests_made += 1
            except httpx.HTTPError as e:
                last_error = e
                continue
            if resp.status_code == 404:
                raise NotFoundError(url)
            if resp.status_code in RETRY_STATUSES:
                last_error = ApiError(f"HTTP {resp.status_code} for {url}")
                continue
            if resp.status_code >= 400:
                raise ApiError(f"HTTP {resp.status_code} for {url}")
            body = resp.content
            try:
                parsed = json.loads(body.decode("utf-8-sig")) if body.strip() else None
            except (ValueError, UnicodeDecodeError):
                parsed = None
            return body, parsed
        raise ApiError(f"giving up on {url} after {self.max_attempts} attempts: {last_error}")

    def close(self) -> None:
        self._client.close()
