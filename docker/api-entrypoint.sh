#!/usr/bin/env sh
# API container entrypoint: run DB migrations, then launch uvicorn.
# `alembic upgrade head` is idempotent — safe to run on every boot. It reads
# DATABASE_URL from the environment (via api.core.config), same as the app.
set -eu

echo "[entrypoint] running alembic upgrade head ..."
alembic upgrade head

echo "[entrypoint] starting uvicorn on 0.0.0.0:8000 ..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
