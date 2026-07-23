"""Test harness: an in-memory SQLite DB (shared via StaticPool) + an ASGI client, with the
DB session dependency overridden. Lets the full API be tested without Docker/Postgres."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.core.config import get_settings
from api.core.security import create_access_token
from api.db.base import Base
from api.db.session import get_session
from api.main import app

# Lifespan-aware tests must never race a real background worker against their isolated DB.
get_settings().generation_worker_enabled = False


def superadmin_headers() -> dict[str, str]:
    """Auth header carrying a first-party super_admin token — the role now required to create a
    tenant (POST /tenants is gated). tenant_id is a non-scoping placeholder; only the role gates."""
    token = create_access_token(tenant_id="platform", role="super_admin")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with test_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()
