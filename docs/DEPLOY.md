# Deploying Mimik Suite (Hetzner VPS + Coolify)

Production deployment runs **pulled** images on a small Hetzner box managed by
Coolify. Postgres is **external** (Supabase); Redis runs as a tiny sidecar
container. This doc covers building images, pushing to GHCR, wiring Coolify, DNS,
and the env vars the operator must set.

---

## ✅ Confirmed VPS state — 2026-07-21 (SSH audit)

`hetzner-vps` = **195.201.33.87** (also the `preview.mimikcreations.com` A record).
- **Ubuntu 24.04.4, 2 vCPU (AMD EPYC), 3.7 GB RAM, 75 GB disk (40 GB free), 2 GB swap.**
  RAM is the binding constraint: **~1.7 GB free, swap already 883 MB used.**
- **Coolify** runs the box (Traefik on 80/443 + coolify-db/redis/realtime) alongside
  **planflow, striker, hermes** (3 Next apps + 2 APIs). Deploy Mimik Suite as a **new
  Coolify resource** — reuse its Traefik/TLS; do NOT hand-roll a second proxy on 80/443.
- **Playwright/Chromium is already on the host** (`~/.cache/ms-playwright/chromium-1208`).
- **~6 GB of reclaimable Docker images** — run `docker image prune -f` on the box to free
  space before pulling (safe; removes only dangling/unused).

**Capacity verdict — it fits, with care.** On-box steady state is light because **Postgres is
external (Supabase)**: web ~200 MB + api idle ~200 MB + redis ~50 MB ≈ **~450 MB**. The risk is
the **Playwright render spike (~400–600 MB)** at archive-on-approval. With ~1.7 GB free + 2 GB
swap and the `mem_limit`s now in `docker-compose.prod.yml` (api 900m / web 450m), a single
serialized render fits. Mitigations if it gets tight: reclaim the 6 GB images; the render is
on-demand + serialized (not steady); temporarily stop planflow/striker for headroom; the
end-of-month RAM upgrade removes the ceiling entirely.

## Image builds run in CI (`.github/workflows/build-images.yml`)

The box can't build the 1.5 GB API image, so a **GitHub Actions workflow** builds both images
(checking out the two private sibling path-deps) and pushes to GHCR on every push to `main`.
**One-time operator setup:** add a repo secret **`GH_PAT`** (a token that can read
`Azi023/mimik-contracts` + `Azi023/mimik-knowledge`); optionally set a repo variable
`NEXT_PUBLIC_API_URL` to the chosen subdomain (baked into the web bundle at build). The GHCR
push uses the built-in `GITHUB_TOKEN`. Then Coolify pulls `ghcr.io/azi023/mimik-suite-{api,web}`.

> **RAM caveat (read first).** The current VPS is 2 vCPU / 4 GB with only
> ~1.8 GB free (Coolify + two other apps already resident). The **API image is
> heavy (~1.5 GB)** because it bundles Playwright + Chromium + system libs —
> `creative/render/compositor.py` and `creative/qa` drive headless Chromium at
> runtime (rendering creatives, contrast sampling). Chromium needs meaningful
> RAM per render. **Do not `docker build` on the VPS** — it will OOM. Build
> elsewhere, pull on the box. Strongly consider upgrading to the **8 GB plan**
> before running real creative renders; 4 GB will be tight and Chromium may be
> OOM-killed under load.

---

## 0. Artifacts in this repo

| File | Purpose |
|---|---|
| `Dockerfile.api` | API image: FastAPI + creative engine + Playwright/Chromium. Runs `alembic upgrade head` then `uvicorn`. |
| `web/Dockerfile` | Web image: Next.js 15 standalone, serves on `:3000`. |
| `docker-compose.prod.yml` | `api` + `web` + `redis`. No postgres (Supabase is external). Healthchecks on all three. |
| `docker/api-entrypoint.sh` | Migrations-then-serve entrypoint for the API. |
| `.dockerignore`, `web/.dockerignore` | Keep venv/node_modules/.next/secrets/var out of build context. |

---

## 1. Sibling path-deps — how the API build context is resolved

`pyproject.toml` pulls two packages that live **outside this repo**:

```toml
[tool.uv.sources]
mimik-contracts = { path = "../mimik-contracts", editable = true }
mimik-knowledge = { path = "../mimik-knowledge", editable = true }
```

On disk they are true siblings of the repo:

```
~/workspace/
  ├── Mimik_Suite/        (this repo — where Dockerfile.api lives)
  ├── mimik-contracts/    (path dep)
  └── mimik-knowledge/    (path dep)
```

**Chosen approach: build with the PARENT directory as the Docker build
context.** That makes all three sibling dirs visible to the build. Inside the
image we reproduce the same sibling layout under `/app`
(`/app/Mimik_Suite`, `/app/mimik-contracts`, `/app/mimik-knowledge`) so the
`../mimik-contracts` relative paths in `pyproject.toml` resolve **unchanged** —
no edits to `pyproject.toml`, no vendoring, no path rewriting.

The build command therefore runs from the parent and points `-f` at the
Dockerfile inside the repo:

```bash
cd ~/workspace
docker build -f Mimik_Suite/Dockerfile.api -t mimik-suite-api:latest .
```

> Why not vendor the siblings into the repo? Because they are actively edited as
> separate packages (the shared contract + the knowledge/eval layer). Copying
> them in would fork the source of truth. The parent-context build keeps one
> source of truth and stays faithful to `uv.lock`.

> **`.dockerignore` note:** Docker reads `.dockerignore` from the **context
> root**. Since the API context is the parent dir, either copy this repo's
> `.dockerignore` up to `~/workspace/.dockerignore` before building, or rely on
> the fact that every `COPY` in `Dockerfile.api` is path-scoped
> (`Mimik_Suite/`, `mimik-contracts/`, `mimik-knowledge/`) so unrelated files in
> the parent are never pulled in. The provided `.dockerignore` uses `**/`
> globs so it works from either context root.

The **web** image has no external deps, so its context is just `./web`
(standard).

---

## 2. Build the images locally (or in CI)

```bash
cd ~/workspace

# --- API (context = parent) ---
docker build -f Mimik_Suite/Dockerfile.api -t mimik-suite-api:latest .

# --- WEB (context = ./web). NEXT_PUBLIC_* is inlined at BUILD time, so the
#     public API origin must be baked in here, not at runtime. ---
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://suite.mimikcreations.com/api \
  -f Mimik_Suite/web/Dockerfile \
  -t mimik-suite-web:latest \
  Mimik_Suite/web
```

> If you also expose the first-party bootstrap bearer (`NEXT_PUBLIC_DEV_TOKEN`),
> pass it as another `--build-arg`. It is inlined into the client bundle, so it
> must be a low-privilege token, never a real secret.

Cross-arch note: build for the VPS architecture. Hetzner Cloud CX/CPX is x86-64,
so build `linux/amd64`. On an Apple-silicon Mac add
`--platform linux/amd64` (or use `docker buildx`).

---

## 3. Push to GitHub Container Registry (ghcr.io)

```bash
# One-time: a classic PAT with `write:packages` (and `read:packages`).
export CR_PAT=ghp_xxxxxxxxxxxxxxxxxxxx
echo "$CR_PAT" | docker login ghcr.io -u <your-github-username> --password-stdin

# Tag to your GHCR namespace (lowercase owner).
docker tag mimik-suite-api:latest ghcr.io/<owner>/mimik-suite-api:latest
docker tag mimik-suite-web:latest ghcr.io/<owner>/mimik-suite-web:latest

# Push.
docker push ghcr.io/<owner>/mimik-suite-api:latest
docker push ghcr.io/<owner>/mimik-suite-web:latest
```

Prefer an immutable tag per release (e.g. a short git SHA) over `:latest` so
rollbacks are deterministic: `ghcr.io/<owner>/mimik-suite-api:$(git rev-parse --short HEAD)`.

If the packages are private, give Coolify pull access: either make the GHCR
packages public (Package settings → Change visibility) or add a registry
credential in Coolify (Settings → Docker Registries) using the same PAT.

---

## 4. Coolify setup

Two workable paths; pick one.

### Option A — deploy from `docker-compose.prod.yml` (recommended)

1. Coolify → **+ New** → **Docker Compose** (Empty / from Git).
2. Point it at this repo (or paste the compose file). Set the compose path to
   `docker-compose.prod.yml`.
3. Set the image tag variables so Coolify **pulls** rather than builds:
   - `API_IMAGE=ghcr.io/<owner>/mimik-suite-api:latest`
   - `WEB_IMAGE=ghcr.io/<owner>/mimik-suite-web:latest`
4. Add the env vars from §6 (Coolify → the resource → **Environment Variables**).
   Coolify materialises these into the `.env` that `env_file: .env` reads.
5. Assign the domain to the **web** service (port 3000) and let Coolify's proxy
   (Traefik) terminate TLS. Route `/api` → the **api** service (port 8000) —
   either a second Traefik rule or a path-based route — matching
   `NEXT_PUBLIC_API_URL=https://suite.mimikcreations.com/api`.
6. Deploy. Coolify pulls the images, starts redis → api (waits healthy) → web.

### Option B — two separate "Docker Image" resources

Create one resource per image (`api`, `web`) referencing the GHCR tags, add a
`redis:7-alpine` resource, set the same env vars, and wire the same domain/route
split. Compose (Option A) is less fiddly because dependency order + healthchecks
are already encoded.

**Migrations** run automatically on API container start (`alembic upgrade head`
in the entrypoint), against the external Supabase `DATABASE_URL`. No manual step.

---

## 5. DNS (Spaceship stays authoritative for the apex)

Keep the main marketing site on Spaceship untouched. Add **one A record** for
the app subdomain pointing at the VPS:

| Type | Host | Value | TTL |
|---|---|---|---|
| A | `suite` | `<VPS_PUBLIC_IP>` | 300 (raise later) |

Result: `suite.mimikcreations.com` → VPS. The apex `mimikcreations.com` and
`www` continue to resolve wherever Spaceship already points them. After DNS
propagates, Coolify/Traefik issues the Let's Encrypt cert for
`suite.mimikcreations.com` on first request.

---

## 6. Environment variables to set in Coolify

Enumerated from `api/core/config.py` + `os.environ` reads across `api/` and
`creative/`. **Set secrets only in Coolify's env UI — never commit them.**

### Required

| Var | Notes |
|---|---|
| `DATABASE_URL` | Supabase Postgres, **asyncpg** driver: `postgresql+asyncpg://postgres:<pw>@db.<ref>.supabase.co:5432/postgres`. Alembic uses this same URL. |
| `REDIS_URL` | `redis://redis:6379/0` (the compose sidecar). Compose already sets this; only override if you move Redis. |
| `JWT_SECRET` | ≥32 chars. Generate: `openssl rand -hex 32`. First-party HS256 signing. |
| `APP_ENV` | `prod`. |

### Auth (Supabase) — required in production (P3)

| Var | Notes |
|---|---|
| `SUPABASE_URL` | `https://<ref>.supabase.co`. Derives the JWKS URL + issuer automatically. |
| `SUPABASE_ANON_KEY` | Public — used by the web client SDK for login. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side admin; never sent to the browser. |
| `SUPABASE_JWT_SECRET` | **Only** for legacy HS256-signing projects. Leave empty for the asymmetric/JWKS default. |

### Copy generation (Gemini, free tier) — P2

| Var | Notes |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key. Enables text/copy enrichment; features degrade gracefully without it. |
| `GEMINI_TEXT_MODEL` | Optional, default `gemini-flash-latest`. |

### Archive backend — P3

| Var | Notes |
|---|---|
| `ARCHIVE_BACKEND` | `local` or `google_drive`. Production = `google_drive`. |
| `ARCHIVE_LOCAL_ROOT` | Only for `local` backend (default `./_archive`). |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Required if `google_drive`. The SA JSON itself or a path to it. Provide via a Coolify secret / mounted file — do **not** bake into the image. |
| `DRIVE_ROOT_FOLDER_ID` | Required if `google_drive`. The "Mimik Clients" shared-drive folder id. |

### Imagery adapters — optional (paid, hard-gated)

| Var | Notes |
|---|---|
| `IMAGE_BACKEND_PRIMARY` | `none` (placeholder, free) for dev/test; a paid backend for real deliverables. |
| `IMAGE_BACKEND_HERO` | `gpt_image` \| `openrouter` \| `gemini_image`. |
| `MIMIK_ALLOW_PAID_IMAGES` | Must be **exactly `1`** to permit any paid image call; every paid adapter refuses otherwise. Leave empty to stay free. |
| `OPENAI_API_KEY`, `OPENAI_IMAGE_MODEL` | For the `gpt_image` adapter. |
| `OPENROUTER_API_KEY`, `OPENROUTER_IMAGE_MODEL` | For the `openrouter` adapter. |
| `GEMINI_IMAGE_MODEL` | For the `gemini_image` adapter (billing on the Gemini key). |

### Billing (Stripe TEST mode) — optional (P5)

| Var | Notes |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_...`. `/billing/checkout` returns 503 until set. |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...`. `/billing/webhook` returns 503 until set. |
| `STRIPE_PRICE_ID` | The recurring price id (test mode). |
| `BILLING_SUCCESS_URL`, `BILLING_CANCEL_URL` | Storefront return URLs (sensible defaults in config). |

### Web image (BUILD-time, not runtime)

| Var | Notes |
|---|---|
| `NEXT_PUBLIC_API_URL` | Inlined at build. `https://suite.mimikcreations.com/api`. |
| `NEXT_PUBLIC_DEV_TOKEN` | Optional low-privilege bootstrap bearer; inlined at build. Never a real secret. |

---

## 7. Validate before shipping

```bash
# Compose parses clean (does NOT build):
docker compose -f docker-compose.prod.yml config >/dev/null && echo OK

# Optional: lint the Dockerfiles without building (BuildKit linter):
docker build --check -f Dockerfile.api ..
docker build --check -f web/Dockerfile ./web
```

## 8. Post-deploy smoke test

```bash
curl -fsS https://suite.mimikcreations.com/api/openapi.json | head -c 200   # API up + migrated
curl -fsS https://suite.mimikcreations.com/ | head -c 200                    # Web up
```

If the API container restarts in a loop, first suspect (a) a bad
`DATABASE_URL` (migrations fail on boot → entrypoint exits) or (b) Chromium
OOM-kill under RAM pressure → move to the 8 GB plan.
