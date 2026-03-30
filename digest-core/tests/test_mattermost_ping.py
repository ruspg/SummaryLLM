"""Tests for Mattermost webhook ping helper."""

import httpx
import pytest

from digest_core.config import MattermostDeliverConfig
from digest_core.deliver.mattermost import DEFAULT_PING_TEXT, ping_mattermost_webhook


def test_ping_mattermost_webhook_ok(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            calls.append({"url": url, "json": json})
            return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setenv("MM_WEBHOOK_URL", "https://mm.example/hooks/abc")
    monkeypatch.setattr("digest_core.deliver.mattermost.httpx.Client", FakeClient)

    status = ping_mattermost_webhook(MattermostDeliverConfig())

    assert status == 200
    assert len(calls) == 1
    assert calls[0]["json"]["text"] == DEFAULT_PING_TEXT


def test_ping_mattermost_webhook_custom_message(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setenv("MM_WEBHOOK_URL", "https://mm.example/hooks/abc")
    monkeypatch.setattr("digest_core.deliver.mattermost.httpx.Client", FakeClient)

    status = ping_mattermost_webhook(
        MattermostDeliverConfig(), text="**custom** ping"
    )
    assert status == 200


def test_ping_mattermost_webhook_http_error(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            req = httpx.Request("POST", url)
            return httpx.Response(404, request=req)

    monkeypatch.setenv("MM_WEBHOOK_URL", "https://mm.example/hooks/bad")
    monkeypatch.setattr("digest_core.deliver.mattermost.httpx.Client", FakeClient)

    with pytest.raises(httpx.HTTPStatusError):
        ping_mattermost_webhook(MattermostDeliverConfig())
