"""Swappable email delivery adapter tests.

All SMTP behavior is exercised through the synchronous `_send_smtp` seam. Tests never open a
network connection and never put a real credential in settings or logs.
"""

from __future__ import annotations

import logging

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
