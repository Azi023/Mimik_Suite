# Mimik Suite

Multi-tenant, done-for-you creative-agency SaaS. Onboard a client → auto brand brief →
hybrid 5-layer creative engine → human-gated review → client approval → auto-archive.
Learns per-client preferences over time. Built to run Mimik/Jasmine's own client work and
be sold as a productized service.

See `CLAUDE.md` for constraints and `HANDOFF.md` for current state.
Full plan: `~/.claude/plans/hi-i-want-to-sunny-fox.md`.

## Layout

```
Mimik_Suite/
  api/        FastAPI + async SQLAlchemy + Alembic + Postgres + Redis + Arq queue
  web/        Next.js (App Router) dashboard  [structure only until a design reference exists]
  creative/   the hybrid 5-layer creative engine (imagery adapters + Playwright compositor)
  tests/      pytest
```

Sibling packages (separate folders, path deps):
- `../mimik-contracts` — Pydantic schema vocabulary
- `../mimik-knowledge` — prompts, golden set, rubrics, evals, learning-loop

## Dev quickstart

```bash
uv sync                       # install deps (Python 3.12)
docker compose up -d          # Postgres + Redis
uv run alembic upgrade head   # apply migrations
uv run uvicorn api.main:app --reload
uv run pytest                 # tests (incl. tenant-isolation IDOR guard)
```

## Status

P0 (foundations) in progress. See `HANDOFF.md`.
