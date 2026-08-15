import httpx
import pytest

from ingest.client import ApiError, NotFoundError, PoliteClient


class FakeTime:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, d):
        self.sleeps.append(d)
        self.t += d


def make_client(handler, fake, min_interval=2.0, max_attempts=4):
    return PoliteClient(
        min_interval=min_interval,
        max_attempts=max_attempts,
        transport=httpx.MockTransport(handler),
        sleep=fake.sleep,
        clock=fake.clock,
    )


def test_paces_requests_two_seconds_apart():
    fake = FakeTime()
    client = make_client(lambda req: httpx.Response(200, json={"a": 1}), fake)
    client.get_json("https://x.test/one")
    client.get_json("https://x.test/two")
    client.get_json("https://x.test/three")
    assert fake.sleeps == [pytest.approx(2.0), pytest.approx(2.0)]
    assert client.requests_made == 3


def test_retries_on_5xx_with_backoff_then_succeeds():
    fake = FakeTime()
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(500) if len(calls) < 3 else httpx.Response(200, json={"ok": 1})

    client = make_client(handler, fake)
    body, parsed = client.get_json("https://x.test/flaky")
    assert parsed == {"ok": 1}
    assert len(calls) == 3
    assert 2.0 in fake.sleeps and 4.0 in fake.sleeps  # exponential backoff


def test_gives_up_after_max_attempts():
    fake = FakeTime()
    client = make_client(lambda req: httpx.Response(503), fake, max_attempts=3)
    with pytest.raises(ApiError, match="giving up"):
        client.get_json("https://x.test/down")
    assert client.requests_made == 3


def test_404_raises_not_found_immediately():
    fake = FakeTime()
    client = make_client(lambda req: httpx.Response(404), fake)
    with pytest.raises(NotFoundError):
        client.get_json("https://x.test/nope")
    assert client.requests_made == 1


def test_other_4xx_is_fatal():
    fake = FakeTime()
    client = make_client(lambda req: httpx.Response(403), fake)
    with pytest.raises(ApiError, match="403"):
        client.get_json("https://x.test/denied")


def test_non_json_body_returns_none():
    fake = FakeTime()
    client = make_client(lambda req: httpx.Response(200, content=b"not json"), fake)
    body, parsed = client.get_json("https://x.test/weird")
    assert body == b"not json" and parsed is None


def test_bom_and_empty_bodies():
    fake = FakeTime()
    client = make_client(lambda req: httpx.Response(200, content="﻿{\"a\":1}".encode()), fake)
    _, parsed = client.get_json("https://x.test/bom")
    assert parsed == {"a": 1}
    client2 = make_client(lambda req: httpx.Response(200, content=b""), fake)
    _, parsed2 = client2.get_json("https://x.test/empty")
    assert parsed2 is None
