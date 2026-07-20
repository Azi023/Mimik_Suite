# Next session — paste-in prompt + context

> Read `HANDOFF.md` (top entry) first — it's the ground truth. This file is the starter prompt
> and the shortlist of what's deferred.

## THE PASTE-IN PROMPT (copy into a fresh session)

> Continue Mimik Suite. Read `HANDOFF.md` (top entry), `CLAUDE.md`, then this file. Verify state:
> `docker compose up -d` then `uv run --no-sync pytest` (expect green) + `cd ../mimik-contracts &&
> uv run --no-sync pytest`. Everything G1–G3 + FE + auth + the Leonardo stealth harness is built,
> committed, and green. **This session's job: build the WhatsApp notification adapter** behind the
> existing `NotificationChannel.WHATSAPP` seam (it's a stub today). Decide WAHA vs OpenWA vs Meta
> Cloud API for MY needs (low-volume outbound: "your creative is ready, review here <magic-link>"),
> keep it swappable like the image backends, and honor every locked constraint (uv run --no-sync;
> tenant authZ at the data layer; secrets only in .env; no shell=True with untrusted input; test
> stub day 1). Pause at human gates (any account/API signup, paid anything, commit). Tell me the
> exact .env values you need before each step.

## Deferred items (shortlist — don't overload, pick per session)

1. **WhatsApp adapter** (this session's focus). Seam: `NotificationChannel.WHATSAPP`. Options —
   WAHA (self-host Docker, HTTP, free) / OpenWA (Node, $6) / Meta Cloud (official, 1k free convos/mo,
   needs Business verification). Use = outbound review-ready notices with the magic-link.
2. **Leonardo**: migrate to the API when the payment issue clears (adapter swap, one config line).
   Meanwhile the burner browser harness works. **Ban-test discipline: run realistic volume on the
   BURNER for ~2 days before touching the main subscription account.** Model IS selectable (URL
   `?model=…`; Phoenix worked) — a small "select model/style" UI-automation enhancement is open.
3. **ChatGPT-image adapter**: OpenAI is logged into the same debug Chrome; confirmed drivable via the
   same CDP-attach + patchright pattern (`_pick_page` isolates tabs). Free tier = rate-limited image gen.
4. **Product UX**: because generation is human-paced (not instant), the flow should surface a
   **"generating / pending delivery" state** (the `JobStatus.GENERATING` already exists) rather than
   imply real-time — a small FE/flow touch until the API path makes it fast.
5. **Deploy**: `docs/DEPLOY.md` is parked (Coolify + Supabase-Postgres on Hetzner). Needs the 8 GB
   VPS upgrade (current 4 GB can't hold the Chromium-bearing API image alongside Coolify).
6. **Housekeeping**: change the two temp login passwords; optionally rotate the 4 keys that hit a
   subagent transcript during deploy-artifact validation.

## Anti-detection stack (as built — for the Leonardo/ChatGPT harness)
`scripts/chrome_debug.py` launches your REAL Chrome (bundle id, debug port :9222, isolated profile)
→ you log in as a human (Cloudflare passes) → the adapter attaches via CDP using **patchright**
(hides `Runtime.enable`) → drives only the target tab → widened human pacing + `human_cooldown`
between generations. Never launches a bot browser, never headless.
