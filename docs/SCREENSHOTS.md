# Playwright screenshots — how to verify screens (light + dark)

> The "human-gate" step: capture each screen in both themes before calling it visually verified.
> This needs REAL data (the dev-token path is read-only, so mutations 401), so we seed via a
> first-party owner token. One-time setup, then a repeatable script per screen.

## Why it isn't automatic
The app renders from the live API when `NEXT_PUBLIC_API_URL` is set AND a bearer resolves. For
screenshots we want populated screens, so we mint a **super_admin → owner token**, seed a tenant with
demo data, and point the web app at it. The screens themselves are the same code paths users hit.

## One-time setup

```bash
# 0. services up (Postgres :5434, Redis :6381)
docker compose up -d

# 1. run the API (own terminal)
uv run --no-sync uvicorn api.main:app --port 8000

# 2. mint an owner token: super_admin -> POST /tenants -> owner access_token
#    (super_admin token is minted in-process; see tests/conftest.py::superadmin_headers)
uv run --no-sync python -c "
from api.core.security import create_access_token
print(create_access_token(tenant_id='platform', role='super_admin'))
"
# -> use it as: curl -H "Authorization: Bearer <SA>" -X POST localhost:8000/tenants \
#      -d '{\"name\":\"Demo\",\"slug\":\"demo\"}' -H 'Content-Type: application/json'
#    the response.access_token is the OWNER token for the demo tenant.

# 3. seed demo data with the owner token: clients -> brands -> pillars -> briefs -> jobs ->
#    creatives -> a magic link. (A seed script lives per-feature; e.g. the kit editor already had
#    web/scripts/seed-*.ts — follow that pattern, or curl the endpoints in order.)

# 4. point the web app at the API + owner token, in dev mode
#    web/.env.local:
#      NEXT_PUBLIC_API_URL=http://localhost:8000
#      NEXT_PUBLIC_DEV_TOKEN=<OWNER_TOKEN>
#      APP_ENV=dev
#    then: (in web/) npx next dev -p 3001   # a FREE port

# ⚠ NEVER run `next build` while `next dev` runs on the same dir — it corrupts .next.
#   If it happens: rm -rf web/.next && restart dev.
```

## The screenshot script (per screen, light + dark)

```js
// web/scripts/shoot.mjs  — run: node scripts/shoot.mjs /calendar calendar
import { chromium } from "playwright";
const [route, name] = process.argv.slice(2);
const base = "http://localhost:3001";
const browser = await chromium.launch();
for (const theme of ["light", "dark"]) {
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 1024 },
    colorScheme: theme, // drives the app's prefers-color-scheme + [data-theme]
  });
  const page = await ctx.newPage();
  await page.goto(`${base}${route}`, { waitUntil: "networkidle" });
  // theme is stored client-side; force it so both variants are deterministic:
  await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
  await page.waitForTimeout(300);
  await page.screenshot({ path: `shots/${name}-${theme}.png`, fullPage: true });
  await ctx.close();
}
await browser.close();
```

### Per-screen notes
- **Full-page shots**: the `.brief` / `.kit` / `.wiz` / `.creview__rail` containers are their own scroll
  containers — for a full-page capture, flatten their `max-height`/`overflow` first:
  ```js
  await page.addStyleTag({ content: `.creview__rail,.brief,.kit,.wiz{max-height:none!important;overflow:visible!important}` });
  ```
- **Review screen** needs a job WITH a creative (seed a CreativeDoc) or you'll shoot the empty state.
- **Magic portal** (`/review/<token>`) needs a minted magic-link token in the URL.
- **Portal** (`/portal`) needs a client-role Supabase session — or shoot it via the owner token in dev
  (it renders; the role-gate only redirects a real client session).

## Routes worth capturing
`/login` · `/` (board) · `/members` · `/briefs/[id]` · `/onboarding` · `/brands/[id]/kit` ·
`/jobs/[id]/review` · `/portal` · `/portal/jobs/[id]` · `/review/[token]` · `/calendar` · `/tasks` ·
`/deliveries` · `/billing`
