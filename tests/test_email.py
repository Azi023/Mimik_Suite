"""Swappable email delivery adapter tests.

All SMTP and Graph behavior is exercised through synchronous HTTP/send seams. Tests never open a
network connection and never put a real credential in settings or logs.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from api.core import config
from api.services import email


def _settings(monkeypatch, **overrides) -> None:
    settings = config.get_settings()
    values = {
        "email_provider": "none",
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_from": "",
        "smtp_use_tls": True,
        **overrides,
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


async def test_none_provider_is_inert_and_returns_recorded(monkeypatch, caplog) -> None:
    _settings(monkeypatch, email_provider="none")

    def unexpected_send(*args, **kwargs) -> None:
        raise AssertionError("none provider must not touch SMTP")

    monkeypatch.setattr(email, "_send_smtp", unexpected_send)

    with caplog.at_level(logging.INFO, logger="api.services.email"):
        result = await email.send_email(
            to="invitee@example.com",
            subject="You're invited to Mimik Suite",
            body_text="https://example.com/invite/accept?token=secret-token",
        )

    assert result.provider == "none"
    assert result.status == "recorded"
    assert result.error is None
    assert "email provider is 'none'" in caplog.text
    assert "secret-token" not in caplog.text


async def test_console_provider_logs_full_message(monkeypatch, caplog) -> None:
    _settings(monkeypatch, email_provider="console")

    with caplog.at_level(logging.INFO, logger="api.services.email"):
        result = await email.send_email(
            to="invitee@example.com",
            subject="You're invited to Mimik Suite",
            body_text="Plain invitation body",
            body_html="<p>HTML invitation body</p>",
        )

    assert result.provider == "console"
    assert result.status == "recorded"
    assert "invitee@example.com" in caplog.text
    assert "You're invited to Mimik Suite" in caplog.text
    assert "Plain invitation body" in caplog.text
    assert "<p>HTML invitation body</p>" in caplog.text


async def test_smtp_failure_is_fail_soft_and_does_not_log_password(
    monkeypatch, caplog
) -> None:
    _settings(
        monkeypatch,
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_username="mailer",
        smtp_password="never-log-this",
        smtp_from="hello@example.com",
    )

    def fail_send(*args, **kwargs) -> None:
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(email, "_send_smtp", fail_send)

    with caplog.at_level(logging.ERROR, logger="api.services.email"):
        result = await email.send_email(
            to="invitee@example.com",
            subject="You're invited to Mimik Suite",
            body_text="Invitation body",
        )

    assert result.provider == "smtp"
    assert result.status == "failed"
    assert result.error == "SMTP unavailable"
    assert "never-log-this" not in caplog.text


def _graph_settings(monkeypatch, **overrides) -> None:
    values = {
        "email_provider": "graph",
        "graph_tenant_id": "tenant-id",
        "graph_client_id": "client-id",
        "graph_client_secret": "never-log-this-graph-secret",
        "graph_sender": "sender@example.com",
        **overrides,
    }
    monkeypatch.setattr(email, "get_settings", lambda: SimpleNamespace(**values))
    monkeypatch.setattr(email, "_graph_token_cache", None, raising=False)


def test_graph_config_has_secret_free_defaults() -> None:
    settings = config.Settings(_env_file=None)

    assert settings.graph_tenant_id == ""
    assert settings.graph_client_id == ""
    assert settings.graph_client_secret == ""
    assert settings.graph_sender == ""


async def test_graph_provider_builds_token_request_and_send_mail_payload(
    monkeypatch, caplog
) -> None:
    _graph_settings(monkeypatch)
    token_requests: list[tuple[str, dict[str, str]]] = []
    mail_requests: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def fake_post_form(url: str, fields: dict[str, str]) -> dict[str, object]:
        token_requests.append((url, fields))
        return {"access_token": "graph-access-token", "expires_in": 3600}

    def fake_post_json(
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> None:
        mail_requests.append((url, headers, payload))

    monkeypatch.setattr(email, "_post_form", fake_post_form, raising=False)
    monkeypatch.setattr(email, "_post_json", fake_post_json, raising=False)

    with caplog.at_level(logging.INFO, logger="api.services.email"):
        result = await email.send_email(
            to="invitee@example.com",
            subject="You're invited to Mimik Suite",
            body_text="Plain invitation body",
            body_html="<p>HTML invitation body</p>",
        )

    assert result == email.EmailResult(provider="graph", status="sent")
    assert "never-log-this-graph-secret" not in caplog.text
    assert "graph-access-token" not in caplog.text
    assert token_requests == [
        (
            "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/token",
            {
                "client_id": "client-id",
                "client_secret": "never-log-this-graph-secret",
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
        )
    ]
    assert mail_requests == [
        (
            "https://graph.microsoft.com/v1.0/users/sender@example.com/sendMail",
            {
                "Authorization": "Bearer graph-access-token",
                "Content-Type": "application/json",
            },
            {
                "message": {
                    "subject": "You're invited to Mimik Suite",
                    "body": {
                        "contentType": "HTML",
                        "content": "<p>HTML invitation body</p>",
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": "invitee@example.com"}},
                    ],
                }
            },
        )
    ]


async def test_graph_provider_uses_text_body_and_cached_token(monkeypatch) -> None:
    _graph_settings(monkeypatch)
    token_requests = 0
    payloads: list[dict[str, object]] = []

    def fake_post_form(url: str, fields: dict[str, str]) -> dict[str, object]:
        nonlocal token_requests
        token_requests += 1
        return {"access_token": "cached-token", "expires_in": 3600}

    def fake_post_json(
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> None:
        payloads.append(payload)

    monkeypatch.setattr(email, "_post_form", fake_post_form, raising=False)
    monkeypatch.setattr(email, "_post_json", fake_post_json, raising=False)

    first = await email.send_email(
        to="first@example.com",
        subject="First invitation",
        body_text="First plain body",
    )
    second = await email.send_email(
        to="second@example.com",
        subject="Second invitation",
        body_text="Second plain body",
    )

    assert first.status == "sent"
    assert second.status == "sent"
    assert token_requests == 1
    assert payloads[0]["message"]["body"] == {
        "contentType": "Text",
        "content": "First plain body",
    }


async def test_graph_auth_failure_is_fail_soft_and_does_not_log_secret(
    monkeypatch, caplog
) -> None:
    secret = "never-log-this-graph-secret"
    _graph_settings(monkeypatch, graph_client_secret=secret)

    def fail_auth(url: str, fields: dict[str, str]) -> dict[str, object]:
        raise OSError("Graph token endpoint unavailable")

    def unexpected_send(*args, **kwargs) -> None:
        raise AssertionError("sendMail must not run after an auth failure")

    monkeypatch.setattr(email, "_post_form", fail_auth, raising=False)
    monkeypatch.setattr(email, "_post_json", unexpected_send, raising=False)

    with caplog.at_level(logging.ERROR, logger="api.services.email"):
        result = await email.send_email(
            to="invitee@example.com",
            subject="You're invited to Mimik Suite",
            body_text="Invitation body",
        )

    assert result.provider == "graph"
    assert result.status == "failed"
    assert result.error == "Graph token endpoint unavailable"
    assert secret not in caplog.text
