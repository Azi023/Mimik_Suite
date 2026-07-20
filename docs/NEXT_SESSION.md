# Next session — FRONTEND build (paste-in prompt + context)

> Read `HANDOFF.md` (top entry) first — ground truth. This file is the starter prompt for the
> dedicated **frontend session**. Everything below is committed on `main` (local; no git remote).

## THE PASTE-IN PROMPT (copy into a fresh session after /clear)

> Continue Mimik Suite — this is the dedicated FRONTEND session. Read `HANDOFF.md` (top entry),
> `CLAUDE.md`, `docs/DESIGN_REFERENCES.md` (LOCKED design system), and `docs/BRAND_KIT_ONBOARDING.md`
> (Zaid's brand-kit/onboarding/designer spec) before touching anything. Verify: `docker compose up -d`
> then `uv run --no-sync pytest -q` (expect 348) + `cd ../mimik-contracts && uv run --no-sync pytest -q`
> (expect 14); in `web/`: `npx tsc --noEmit` + `npx next build` (expect clean). Everything backend is
> green; login + members/roles screens are built (shadcn mono admin look, light+dark, on the existing
> token system in `web/design/tokens.css` — NOT tailwind/shadcn; we match the look with tokens).
>
> **Design rules (locked):** build on **Opus** (not Fable). Match `docs/DESIGN_REFERENCES.md`: shadcn
> "Studio Admin" north-star, mono monochrome, light+dark, real empty states (NO mock fallback — kill
> `web/lib/data.ts` mock as each screen lands), preserve Supabase auth wiring + tenant-scoped API calls,
> no `any` / explicit return types. Mutations go through **Next.js server actions** (read the httpOnly
> session cookie server-side) like `web/app/members/actions.ts` — not client fetch.
>
> **This session — build these screens in order** (backend for all of them already exists):
> 1. **Brand-brief editor + sign-off** (clearest client "wow"; `Brief`/`BriefSections` + `POST
>    /briefs/{id}/signoff` + `/revise` exist). View the 9 sections, edit, sign-off (freeze→version).
> 2. **Onboarding wizard** (Brand → Brand Kit → Content Pillars → Style reference; endpoints exist).
> 3. **Brand-kit editor + the NEW Layout box** (logo-position 3×3 picker, header/footer, margins) —
>    needs a small contract add `BrandLayout` on `BrandTokens` (see BRAND_KIT_ONBOARDING.md §3) + wire
>    the compositor. Schema-first.
>
> Pause at human gates (contract changes, commits). Show a screenshot (Playwright, light+dark) of each
> screen before committing. Keep every screen behind the Supabase session gate like `web/app/members/`.

## State at handoff (2026-07-20 late-night, `main` = `5d22df8`)
- Backend: 348 Suite / 14 contracts green, ruff clean. IAM done (super_admin gate, invitations,
  capability matrix, client_scopes). WhatsApp adapter inert (blocked on Meta portfolio). ChatGPT +
  Leonardo image adapters built. Generating/pending state shipped.
- Frontend built: **login** (`web/app/login`), **members/roles** (`web/app/members`). Board pre-existed.
- Design system LOCKED (`docs/DESIGN_REFERENCES.md`); Zaid's designer spec (`docs/BRAND_KIT_ONBOARDING.md`).

## Deferred / open loops (not this session unless noted)
1. **Full tailwind+shadcn adoption** in `web/` — currently we MATCH the shadcn look with the token-CSS
   system (no tailwind). A real migration touches every component; decide deliberately before doing it.
2. **Wire scope-filtering into query routes** — `is_client_in_scope`/`principal_client_ids` exist
   (IAM increment B) but aren't enforced on reads yet (empty scope = all = current behavior).
3. **Kill the `web/lib/data.ts` mock-fallback** — do it per-screen as real screens with empty states land.
4. **WhatsApp**: fresh clean Meta business portfolio (24h name-hold was blocking) → then activate.
5. **Client portal + creative review** (Filestage ref) and **video review** (Frame.io ref) — later screens.
6. **Housekeeping**: change the 2 temp login passwords; art-direction rubric from the 17 principles.
7. **No git remote** configured — commits are local only. Add a remote + push if you want offsite backup.

## Reference images
UI screenshots (shadcn admin, Filestage, Frame.io) are captured by **URL + description** in
`docs/DESIGN_REFERENCES.md` (raw PNGs were transient). `docs/design-refs/17-design-principles.png` is
saved. Re-drop any reference you want archived and it'll be copied into `docs/design-refs/`.
