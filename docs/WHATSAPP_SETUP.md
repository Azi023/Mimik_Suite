# WhatsApp outbound — Meta Cloud API setup

The adapter is built and green behind `NotificationChannel.WHATSAPP`. It stays **inert**
(`WHATSAPP_PROVIDER=none`) until the steps below are done and the env is set. Nothing sends,
no account is touched, until you flip the provider. This doc is the human-gated part.

## What the adapter does

`api/services/whatsapp.py` → `MetaCloudWhatsAppSink` sends a **pre-approved Utility template**
whose single body variable `{{1}}` carries the system-composed review magic-link. Business-
initiated messages (our "your creative is ready" nudge) outside the 24h customer-care window
*must* be templates — that's why this is template-based, not free text.

Delivery is tenant-scoped (`dispatch_pending`), the token lives only in the HTTP header (never
logged, never in the payload), and the message body is always a system-composed magic-link —
never client freeform text (locked constraint #3).

## Account-health reality (read first)

The official Cloud API is the **zero-number-ban** path: a number registered to it is *meant*
to be used for automated business messaging and won't be banned for it. The only enforcement
risk here is Meta *policy/account* restrictions (ad bans, "unusual activity") — those flag the
**business/app**, never the phone number. Two of ours are already flagged and must be abandoned:

- **`Mimik Creations` portfolio** — advertising-restricted since Sep 2023 (can't claim apps).
- **`Mimik flow` app (937770042285097)** — restricted for a policy violation (Enforced Mar 29).
- (`Mark Antony` is only an *admin user* on that app — NOT a business portfolio.)

**Verification ≠ un-restriction.** Verifying a business proves identity; it does not lift an
enforcement restriction. Don't waste days appealing 2023 enforcement — start clean instead.

## One-time Meta setup (on a FRESH clean portfolio)

1. **Create a brand-new business portfolio.** `business.facebook.com` → Settings → *Create a
   business portfolio* (do NOT use Mimik Creations). Ideally create/own it from a **clean
   personal FB account** — if the "unusual activity on this developer account" flag is tied to
   the personal account behind Mimik flow, a new app under it can inherit the restriction.
2. **Create a Meta app** at `developers.facebook.com` → *Create App* → **Business** type →
   link it to the **new** portfolio → add the **WhatsApp** product. If Create-App is blocked
   ("business not allowed to claim app"), the personal account is flagged — switch to a clean
   one. Dev testing needs NO business verification.
3. **Dev first — use the free test number.** WhatsApp → *API Setup* gives you a temporary
   **test sender number** and a `Phone number ID`. Add up to ~5 **verified recipient** numbers
   (your own phones) there. This is enough to build/verify end-to-end with **no real number and
   no ban risk**.
4. **Create the Utility template.** WhatsApp → *Message Templates* → Create:
   - Name: `creative_ready` · Category: **Utility** · Language: `en`
   - Body: `Hi! Your new creative is ready to review: {{1}}` (exactly one variable)
   - Sample for `{{1}}`: any https URL. Submit → approval is usually minutes for Utility.
5. **Token.** For dev, the temporary token on the API Setup page works. For anything lasting,
   create a **System User** (Business Settings → System Users) with a **permanent token** scoped
   to `whatsapp_business_messaging` + `whatsapp_business_management`. Treat it as a secret.
6. **Go-live only:** register a **dedicated real number** that is NOT active on the consumer
   WhatsApp / WhatsApp Business app (it receives an OTP during registration and then belongs to
   the Cloud API). Set a display name ("Mimik Creations") — quick Meta review.

## .env values (fill these, then flip the provider)

```
WHATSAPP_PROVIDER=meta_cloud
WHATSAPP_PHONE_NUMBER_ID=<Phone number ID from API Setup — NOT the phone number itself>
WHATSAPP_ACCESS_TOKEN=<system-user permanent token, or the temp dev token>
WHATSAPP_TEMPLATE_NAME=creative_ready
WHATSAPP_TEMPLATE_LANG=en
# WHATSAPP_API_BASE defaults to https://graph.facebook.com/v21.0 — leave unless Meta bumps it
```

The recipient phone comes from `Client.phone` (E.164, e.g. `+9477…`) at notification-creation
time — the sink normalises it to digits. A WHATSAPP notification with no recipient is marked
FAILED (never silently dropped).

## Verifying live (after setup)

Record a WHATSAPP notification for a client whose `phone` is one of your **verified test
recipients**, with `body` = a review magic-link, then run `dispatch_pending` for that tenant.
A message arrives on the test number's linked WhatsApp; the row flips to SENT.

## Still deferred (not this adapter)

- **Composing** the "creative ready" WHATSAPP notification (body = magic-link) at job-delivery
  time — a caller-side helper, separate from this sink.
- **Email channel** (`NotificationChannel.EMAIL`) via **Microsoft Graph `sendMail`** from the
  M365 tenant (`no-reply@mimikcreations.com`), not SMTP. Drops into the same seam as an
  `EmailSink` — a future session.
