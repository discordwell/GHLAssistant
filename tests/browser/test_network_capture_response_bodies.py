"""Unit tests for NetworkCapture response body handling.

We intentionally keep these as pure unit tests (no real browser) by stubbing
the CDP page object and event payloads.
"""

from __future__ import annotations

import pytest

from maxlevel.browser.network import NetworkCapture


class _DummyPage:
    def __init__(self, *, body_result):
        self._body_result = body_result
        self.send_calls: list[object] = []

    async def send(self, cmd):
        self.send_calls.append(cmd)
        # nodriver CDP commands are generators; we only care about get_response_body.
        name = getattr(getattr(cmd, "gi_code", None), "co_name", "")
        if name == "get_response_body":
            return self._body_result
        return {}

    def add_handler(self, *_args, **_kwargs):
        return None


class _DummyReq:
    def __init__(self, *, url: str, method: str, headers: dict, post_data: str | None = None):
        self.url = url
        self.method = method
        self.headers = headers
        self.post_data = post_data


class _DummyRequestEvent:
    def __init__(self, *, request_id: str, url: str):
        self.request_id = request_id
        self.request = _DummyReq(url=url, method="GET", headers={"Accept": "application/json"})


class _DummyResp:
    def __init__(self, *, status: int, headers: dict):
        self.status = status
        self.headers = headers


class _DummyResponseEvent:
    def __init__(self, *, request_id: str, url: str, status: int, headers: dict):
        self.request_id = request_id
        self.response = _DummyResp(status=status, headers=headers)
        self._url = url


class _DummyLoadingFinished:
    def __init__(self, *, request_id: str, encoded_data_length: float = 0.0):
        self.request_id = request_id
        self.encoded_data_length = encoded_data_length


@pytest.mark.asyncio
async def test_network_capture_fetches_body_on_loading_finished():
    page = _DummyPage(body_result=('{"ok":true}', False))
    cap = NetworkCapture(page, capture_response_bodies=True, max_response_body_chars=200_000)

    await cap._on_request(_DummyRequestEvent(request_id="1", url="https://backend.leadconnectorhq.com/foo"))
    await cap._on_response(
        _DummyResponseEvent(
            request_id="1",
            url="https://backend.leadconnectorhq.com/foo",
            status=200,
            headers={"content-type": "application/json"},
        )
    )
    await cap._on_loading_finished(_DummyLoadingFinished(request_id="1", encoded_data_length=20))

    req = cap.requests["1"]
    assert req.response_body == '{"ok":true}'
    assert req.response_body_length == len('{"ok":true}')
    assert req.response_body_truncated is False
    assert req.response_body_base64 is False
    assert len(page.send_calls) == 1


@pytest.mark.asyncio
async def test_network_capture_skips_non_ghl_domains():
    page = _DummyPage(body_result=("should-not-be-fetched", False))
    cap = NetworkCapture(page, capture_response_bodies=True)

    await cap._on_request(_DummyRequestEvent(request_id="1", url="https://example.com/api"))
    await cap._on_response(
        _DummyResponseEvent(
            request_id="1",
            url="https://example.com/api",
            status=200,
            headers={"content-type": "application/json"},
        )
    )
    await cap._on_loading_finished(_DummyLoadingFinished(request_id="1", encoded_data_length=10))

    assert cap.requests["1"].response_body is None
    assert len(page.send_calls) == 0


@pytest.mark.asyncio
async def test_network_capture_skips_huge_bodies_without_fetching():
    page = _DummyPage(body_result=("x" * 999999, False))
    cap = NetworkCapture(page, capture_response_bodies=True, max_response_body_chars=10)

    await cap._on_request(_DummyRequestEvent(request_id="1", url="https://backend.leadconnectorhq.com/big"))
    await cap._on_response(
        _DummyResponseEvent(
            request_id="1",
            url="https://backend.leadconnectorhq.com/big",
            status=200,
            headers={"content-type": "application/json"},
        )
    )
    await cap._on_loading_finished(_DummyLoadingFinished(request_id="1", encoded_data_length=1000))

    req = cap.requests["1"]
    assert req.response_body is None
    assert req.response_body_truncated is True
    assert req.response_body_length == 1000
    assert len(page.send_calls) == 0
