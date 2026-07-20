# Design reference-gathering brief

> How to collect references for the remaining frontend so the whole product feels like ONE product.
> Fill the "your pick" column with a URL or a screenshot path, then we build each screen on **Fable**
> with that reference in hand (locked rule #9: no styling without a concrete reference).

## The one rule that matters

**Pick ONE north-star first — the whole-product visual identity — then gather per-page references
only for LAYOUT / FLOW, not for look.** A separate visual reference per page produces a
stitched-together product. The north-star decides palette, type, density, motion; per-page
references only answer "how is this screen structured."

### Step 1 — choose the north-star (do this before anything else)
Browse 5–8 products, pick the ONE whose overall feel you want Mimik Suite to have. Candidates by vibe:
- **Crisp / keyboard-first / dense** → Linear, Height
- **Calm / content-first / soft** → Notion, Cron/Notion Calendar
- **Technical / minimal / confident** → Vercel, Resend, Railway
- **Media-review / dark / cinematic** → Frame.io  *(closest analog to our creative-review job)*

Your taste anchors from your notes — **impeccable.style** and **uxsculpt.com** — are also fair game.
Save 2–3 full-page screenshots of the winner. That's the system reference.

### Step 2 — per-page LAYOUT references (1–2 each)
For each remaining screen, look at the *direct analog* products below, capture how they lay the
screen out (not their colors — the north-star owns color), and drop a URL/screenshot in "your pick".

| Screen (missing today) | Best analog products to study | What to capture | Your pick |
|---|---|---|---|
| **Onboarding / intake wizard** (new client + URL) | Stripe onboarding, Cal.com setup, Typeform | step progression, one-thing-per-step, URL-in field | |
| **Brand brief editor + sign-off** | Frontify, Brandpad, Standards.site, Notion doc + PandaDoc sign-off | section layout, editable vs frozen state, the sign-off moment | |
| **Creative review + approval** | **Frame.io, Filestage, Ziflow, Pastel, Markup.io** | image-first canvas, comment/annotate, approve / request-change buttons | |
| **Creatives gallery + L1–L5 layers** | Canva/Figma layers panel, Photopea | thumbnail grid + a light "recipe/layers" side panel | |
| **Content calendar** | **Planoly, Later, Buffer, Sprout Social, Metricool** | month grid, per-post cards, at-risk/late badges | |
| **Client portal** (bounded self-serve) | **Copilot (copilot.com), SuperOkay, Moxie, Bonsai** | client's cut-down view, "your designs / approve / ask for changes" | |
| **Settings / members / roles (RBAC)** | Linear settings, Vercel team, WorkOS, Clerk | members table, role dropdowns, invite flow | |
| **Admin onboarding** (new agency + users) | Stripe dashboard, Vercel new-team | create-org → invite → first client | |
| **Billing / subscription** | Stripe customer portal, Linear/Vercel billing | plan card, invoices, manage-subscription | |
| **Ops board** (exists — refine) | Linear board, Trello, Notion board | column density, card anatomy, the generating/pending state | |

## Where to search (fastest → aspirational)
1. **Mobbin** (mobbin.com) — real product screens searchable by app + flow (onboarding, settings…). **Best for layout/flow.** Start here.
2. **Refero** (refero.design) — real SaaS screenshots by page type.
3. **Godly** (godly.website), **SaaSframe**, **Land-book**, **Pageflows** (flow *videos*) — for the north-star hunt.
4. **Dribbble / Behance** — aspiration only; caution, much of it is non-functional eye-candy. Use for a *mood*, never as a literal layout.

## How to hand it to me
- Save screenshots under `docs/design-refs/<screen>/…` (or just paste URLs into the table above).
- One line of intent per reference helps a lot: *"this sidebar", "these cards", "this empty state"*.
- Minimum to start building: **the north-star + one screen's layout reference.** We don't need all
  10 before we begin — send the north-star + whichever screen you want first (I'd suggest the
  **brand-brief** screen: backend's done, and it's the clearest "wow").

## Then the build loop (on Fable)
For each screen: you send north-star + that screen's reference → I run the **frontend-design skill on a
Fable subagent** with your reference + our existing tokens → review → iterate. Structure gets
scaffolded from the real API; styling only ever follows a reference you've given.
