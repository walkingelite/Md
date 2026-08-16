"""Provider webhooks settle unverified sends."""

import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from ai_bos.api.main import app
from ai_bos.api.routers.webhooks import _stripe_signature_valid


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_sendgrid_delivered_settles_the_action():
    with patch("ai_bos.api.routers.webhooks._promote", AsyncMock(return_value=True)) as promote:
        async with await _client() as c:
            r = await c.post(
                "/webhooks/sendgrid",
                json=[{"event": "delivered", "sg_message_id": "abc123.filter001"}],
            )
    assert r.status_code == 200
    assert r.json()["settled"] == 1
    # The provider id is split on the first dot before matching.
    promote.assert_awaited_once_with("abc123", True, "sendgrid")


async def test_sendgrid_bounce_marks_failed():
    with patch("ai_bos.api.routers.webhooks._promote", AsyncMock(return_value=True)) as promote:
        async with await _client() as c:
            await c.post(
                "/webhooks/sendgrid",
                json=[{"event": "bounce", "sg_message_id": "xyz.filter"}],
            )
    promote.assert_awaited_once_with("xyz", False, "sendgrid")


async def test_sendgrid_ignores_intermediate_events():
    with patch("ai_bos.api.routers.webhooks._promote", AsyncMock(return_value=True)) as promote:
        async with await _client() as c:
            r = await c.post(
                "/webhooks/sendgrid",
                json=[{"event": "processed", "sg_message_id": "a.b"},
                      {"event": "open", "sg_message_id": "a.b"}],
            )
    assert r.json()["settled"] == 0
    promote.assert_not_awaited()


async def test_sendgrid_rejects_non_list_payload():
    async with await _client() as c:
        r = await c.post("/webhooks/sendgrid", json={"event": "delivered"})
    assert r.status_code == 400


async def test_twilio_delivered_settles():
    with patch("ai_bos.api.routers.webhooks._promote", AsyncMock(return_value=True)):
        async with await _client() as c:
            r = await c.post(
                "/webhooks/twilio",
                data={"MessageStatus": "delivered", "MessageSid": "SM123"},
            )
    assert r.status_code == 200
    assert r.json()["settled"] is True


async def test_twilio_intermediate_status_is_not_an_outcome():
    async with await _client() as c:
        r = await c.post(
            "/webhooks/twilio", data={"MessageStatus": "queued", "MessageSid": "SM1"}
        )
    assert r.json()["settled"] is False


async def test_stripe_rejects_unsigned_payload():
    """An unsigned payment webhook is an invitation to mark invoices paid."""
    async with await _client() as c:
        r = await c.post("/webhooks/stripe", json={"type": "invoice.paid"})
    assert r.status_code == 400


async def test_stripe_rejects_wrong_signature():
    async with await _client() as c:
        r = await c.post(
            "/webhooks/stripe",
            json={"type": "invoice.paid"},
            headers={"stripe-signature": "t=123,v1=deadbeef"},
        )
    assert r.status_code == 400


def test_stripe_signature_verification_accepts_a_correct_signature():
    secret = "whsec_test_secret"
    payload = b'{"type":"invoice.paid"}'
    ts = str(int(time.time()))
    expected = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    assert _stripe_signature_valid(payload, f"t={ts},v1={expected}", secret)


def test_stripe_signature_verification_rejects_tampered_payload():
    secret = "whsec_test_secret"
    ts = str(int(time.time()))
    expected = hmac.new(
        secret.encode(), f"{ts}.".encode() + b'{"amount":100}', hashlib.sha256
    ).hexdigest()
    assert not _stripe_signature_valid(
        b'{"amount":999999}', f"t={ts},v1={expected}", secret
    )


def test_stripe_signature_rejects_malformed_header():
    for header in ("", "garbage", "t=123", "v1=abc"):
        assert not _stripe_signature_valid(b"{}", header, "secret")
