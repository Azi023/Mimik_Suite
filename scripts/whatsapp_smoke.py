"""Live smoke test for the WhatsApp Meta Cloud sink — sends ONE real template message.

Run AFTER `.env` is filled (WHATSAPP_PROVIDER=meta_cloud + credentials) and the recipient is a
VERIFIED test recipient in Meta's API Setup. This drives the SHIPPED adapter
(`api.services.whatsapp.MetaCloudWhatsAppSink`), so a success here means the production code
path works — not a throwaway.

    uv run --no-sync python scripts/whatsapp_smoke.py --to +9477XXXXXXX \
        --link https://mimikcreations.com/review/demo

Nothing is written to the DB. On failure it prints Meta's response body (operator-local, your
own token/number) so you can see WHY — e.g. template not approved, recipient not allow-listed.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx

from api.core.config import get_settings
from api.db.models import NotificationRow
from api.services.whatsapp import MetaCloudWhatsAppSink, _to_msisdn
from mimik_contracts import NotificationChannel, NotificationStatus


async def main() -> int:
    parser = argparse.ArgumentParser(description="Send one WhatsApp template via the real sink.")
    parser.add_argument("--to", required=True, help="recipient phone, E.164, e.g. +9477XXXXXXX")
    parser.add_argument(
        "--link",
        default="https://mimikcreations.com/review/demo",
        help="the review URL that fills the template's {{1}} slot",
    )
    args = parser.parse_args()

    s = get_settings()
    if s.whatsapp_provider.strip().lower() != "meta_cloud":
        print(f"WHATSAPP_PROVIDER is {s.whatsapp_provider!r} — set it to 'meta_cloud' in .env first.")
        return 2
    if not (s.whatsapp_phone_number_id and s.whatsapp_access_token):
        print("WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN are not set in .env.")
        return 2

    row = NotificationRow(
        id="smoke",
        tenant_id="smoke",
        client_id="smoke",
        channel=NotificationChannel.WHATSAPP.value,
        status=NotificationStatus.PENDING.value,
        subject="Your creative is ready",
        body=args.link,
        recipient=args.to,
    )

    sink = MetaCloudWhatsAppSink()
    await sink.send(row)

    if row.status == NotificationStatus.SENT.value:
        print(f"✅ SENT — a WhatsApp message should arrive on {args.to}. (sent_at={row.sent_at})")
        return 0

    print(f"❌ {row.status.upper()} — not delivered. Fetching Meta's response for the reason…")
    # Diagnostic ONLY: repeat the call directly to surface the response body to the operator's
    # own terminal. The production sink deliberately never logs this (it can echo the token/link).
    url = f"{s.whatsapp_api_base.rstrip('/')}/{s.whatsapp_phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            json=sink._payload(_to_msisdn(args.to), args.link),
            headers={
                "Authorization": f"Bearer {s.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
        )
    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except (ValueError, json.JSONDecodeError):
        print(resp.text[:2000])
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
