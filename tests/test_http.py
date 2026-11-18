import httpx
import pytest

from coletor.http import FetchError, PageBlocked, PoliteClient


class FakeClock:
    def __init__(self):
        self.t = 100.0
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def client(handler, fc):
    return PoliteClient(transport=httpx.MockTransport(handler), sleep=fc.sleep, clock=fc.clock)


def test_waits_min_interval_between_calls():
    fc = FakeClock()
    c = client(lambda r: httpx.Response(200, text="ok"), fc)
    assert c.get("https://loja/a") == "ok"
    fc.t += 1.0
    c.get("https://loja/b")
    assert fc.sleeps == [pytest.approx(2.0)]


def test_sends_portuguese_browser_headers():
    seen = {}

    def handler(r):
        seen.update(r.headers)
        return httpx.Response(200, text="ok")

    client(handler, FakeClock()).get("https://loja/a")
    assert "pt-BR" in seen["accept-language"] and "Mozilla" in seen["user-agent"]


@pytest.mark.parametrize("status", [403, 429])
def test_block_raises_page_blocked_without_retry(status):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(status)

    with pytest.raises(PageBlocked):
        client(handler, FakeClock()).get("https://loja/a")
    assert len(calls) == 1


def test_500_retries_then_fetch_error():
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(500)

    with pytest.raises(FetchError) as e:
        client(handler, FakeClock()).get("https://loja/a")
    assert len(calls) == 3 and not isinstance(e.value, PageBlocked)


def test_timeout_retries_then_fetch_error():
    calls = []

    def handler(r):
        calls.append(r)
        raise httpx.ReadTimeout("lento", request=r)

    with pytest.raises(FetchError):
        client(handler, FakeClock()).get("https://loja/a")
    assert len(calls) == 3


def test_recovers_after_one_500():
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(500) if len(calls) == 1 else httpx.Response(200, text="ok")

    assert client(handler, FakeClock()).get("https://loja/a") == "ok"
