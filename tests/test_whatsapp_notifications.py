"""WhatsApp sink + per-channel dispatch routing — no network, no account, no real Meta call.

The Meta Cloud sink is exercised through an injected `httpx.MockTransport`, so every assertion
about the request payload / headers is made against a captured request, never the wire. The
dispatch-routing test uses the same in-memory-SQLite recipe as `test_at_risk`.
"""

from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db import repo
from api.db.base import Base
from api.db.models import NotificationRow
from api.services.notifications import dispatch_pending, resolve_sink
from api.services.whatsapp import (
    MetaCloudWhatsAppSink,
    NullWhatsAppSink,
    _to_msisdn,
    resolve_whatsapp_sink,
)
from mimik_contracts import NotificationChannel, NotificationStatus


@pytest.fixture(autouse=True)
def _pin_whatsapp_provider_none(monkeypatch) -> None:
    """Hermetic default: ignore any ambient `.env` WHATSAPP_PROVIDER so these tests don't depend
    on the developer's local config. Tests that need another provider monkeypatch it explicitly
    (their setattr runs after this and wins). Meta-sink tests inject creds directly, unaffected."""
    from api.core import config

    monkeypatch.setattr(config.get_settings(), "whatsapp_provider", "none")


@pytest_asyncio.fixture
async def sessionmaker() -> async_sessionmaker:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


def _row(**overrides) -> NotificationRow:
    """A minimal detached NotificationRow for unit-testing a sink in isolation."""
    fields = {
        "id": "n-1",
        "tenant_id": "t-1",
        "client_id": "c-1",
        "channel": NotificationChannel.WHATSAPP.value,
        "status": NotificationStatus.PENDING.value,
        "subject": "Your creative is ready",
        "body": "https://mimikcreations.com/review/abc.magic.link",
        "recipient": "+94 77 123 4567",
    }
    fields.update(overrides)
    return NotificationRow(**fields)


def _mock_meta(handler) -> MetaCloudWhatsAppSink:
    """A meta_cloud sink whose HTTP goes to an injected MockTransport (no network)."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return MetaCloudWhatsAppSink(
        phone_number_id="PN_TEST", access_token="tok_secret", client=client
    )


def test_to_msisdn_strips_formatting() -> None:
    assert _to_msisdn("+94 77 123 4567") == "94771234567"
    assert _to_msisdn(None) == ""
    assert _to_msisdn("  ") == ""


def test_resolve_whatsapp_sink_defaults_to_null(monkeypatch) -> None:
    # Default provider is "none" -> the inert sink (no network, no account).
    sink = resolve_whatsapp_sink()
    assert isinstance(sink, NullWhatsAppSink)


def test_resolve_sink_routes_whatsapp_vs_in_app() -> None:
    assert isinstance(resolve_sink(NotificationChannel.WHATSAPP.value), NullWhatsAppSink)
    # IN_APP is delivered-on-record by the RecordingSink (not a WhatsApp sink).
    assert not isinstance(resolve_sink(NotificationChannel.IN_APP.value), NullWhatsAppSink)


async def test_null_sink_leaves_row_pending() -> None:
    row = _row()
    await NullWhatsAppSink().send(row)
    # Non-destructive: not wired != failed. It stays PENDING for a later configured run.
    assert row.status == NotificationStatus.PENDING.value
    assert row.sent_at is None


async def test_meta_sink_sends_template_and_marks_sent() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.X"}]})

    row = _row()
    await _mock_meta(handler).send(row)

    assert row.status == NotificationStatus.SENT.value
    assert row.sent_at is not None
    # Hits the phone-number-id messages endpoint with the bearer token in the HEADER.
    assert captured["url"].endswith("/PN_TEST/messages")
    assert captured["auth"] == "Bearer tok_secret"
    payload = captured["json"]
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "94771234567"  # normalised, no '+'
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "creative_ready"
    # The magic-link (system-composed, from row.body) fills the single body slot — nothing else.
    param = payload["template"]["components"][0]["parameters"][0]["text"]
    assert param == row.body


async def test_meta_sink_never_puts_token_in_payload() -> None:
    """Secret hygiene: the access token belongs in the header, never the message body/payload."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["raw"] = request.content.decode()
        return httpx.Response(200, json={"messages": [{"id": "wamid.Y"}]})

    await _mock_meta(handler).send(_row())
    assert "tok_secret" not in captured["raw"]


async def test_meta_sink_no_recipient_fails() -> None:
    row = _row(recipient=None)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not be called
        raise AssertionError("must not hit the network without a recipient")

    await _mock_meta(handler).send(row)
    assert row.status == NotificationStatus.FAILED.value
    assert row.sent_at is None


async def test_meta_sink_missing_credentials_fails_without_network() -> None:
    row = _row()

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not hit the network with no credentials")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sink = MetaCloudWhatsAppSink(phone_number_id="", access_token="", client=client)
    await sink.send(row)
    assert row.status == NotificationStatus.FAILED.value


async def test_meta_sink_non_2xx_marks_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad template"}})

    row = _row()
    await _mock_meta(handler).send(row)
    assert row.status == NotificationStatus.FAILED.value
    assert row.sent_at is None


async def test_dispatch_routes_per_channel(sessionmaker) -> None:
    """IN_APP delivers-on-record (SENT); WHATSAPP with the default 'none' provider is left
    PENDING. dispatch_pending returns only the count actually SENT."""
    async with sessionmaker() as session:
        tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
        client = await repo.create_client(session, tenant_id=tenant.id, name="Glo2Go")
        await repo.create_notification(
            session,
            tenant_id=tenant.id,
            client_id=client.id,
            channel=NotificationChannel.IN_APP.value,
            subject="New comment",
        )
        await repo.create_notification(
            session,
            tenant_id=tenant.id,
            client_id=client.id,
            channel=NotificationChannel.WHATSAPP.value,
            subject="Creative ready",
            body="https://mimikcreations.com/review/x.magic.link",
            recipient="+94771234567",
        )
        await session.commit()
        tenant_id = tenant.id

    async with sessionmaker() as session:
        sent = await dispatch_pending(session, tenant_id=tenant_id)

    assert sent == 1  # only the IN_APP row was delivered

    async with sessionmaker() as session:
        notes = await repo.list_notifications(session, tenant_id=tenant_id)
    by_channel = {n.channel: n for n in notes}
    assert by_channel[NotificationChannel.IN_APP.value].status == NotificationStatus.SENT.value
    # WhatsApp left PENDING (no provider wired) — recorded, not lost, not falsely marked sent.
    assert by_channel[NotificationChannel.WHATSAPP.value].status == NotificationStatus.PENDING.value


@pytest.mark.parametrize("provider", ["", "none", "NONE"])
def test_resolve_whatsapp_sink_none_variants(provider, monkeypatch) -> None:
    from api.core import config

    monkeypatch.setattr(config.get_settings(), "whatsapp_provider", provider)
    assert isinstance(resolve_whatsapp_sink(), NullWhatsAppSink)


async def test_bad_provider_aborts_before_mutating_any_row(sessionmaker, monkeypatch) -> None:
    """A misconfigured WHATSAPP_PROVIDER must fail during up-front sink resolution — before any
    row is sent — so an unknown provider can't leave a half-delivered, uncommitted batch."""
    from api.core import config

    monkeypatch.setattr(config.get_settings(), "whatsapp_provider", "bogus")

    async with sessionmaker() as session:
        tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
        client = await repo.create_client(session, tenant_id=tenant.id, name="Glo2Go")
        await repo.create_notification(
            session,
            tenant_id=tenant.id,
            client_id=client.id,
            channel=NotificationChannel.IN_APP.value,
            subject="New comment",
        )
        await repo.create_notification(
            session,
            tenant_id=tenant.id,
            client_id=client.id,
            channel=NotificationChannel.WHATSAPP.value,
            subject="Creative ready",
            recipient="+94771234567",
        )
        await session.commit()
        tenant_id = tenant.id

    async with sessionmaker() as session:
        with pytest.raises(ValueError):
            await dispatch_pending(session, tenant_id=tenant_id)

    # The IN_APP row must NOT have been delivered — resolution failed before the send loop.
    async with sessionmaker() as session:
        notes = await repo.list_notifications(session, tenant_id=tenant_id)
    assert all(n.status == NotificationStatus.PENDING.value for n in notes)
