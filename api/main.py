"""Mimik Suite API entrypoint."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from api.core.config import get_settings
from api.db.session import get_sessionmaker
from api.routers import (
    admin,
    approvals,
    assets,
    billing,
    brands,
    briefs,
    clients,
    creatives,
    deliveries,
    exports,
    fonts,
    intake,
    invitations,
    jobs,
    me,
    ops,
    pillars,
    portal,
    preferences,
    tasks,
    tenants,
)
from api.services.generation_worker import run_worker


logger = logging.getLogger(__name__)
_WORKER_SHUTDOWN_TIMEOUT = 5.0


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    stop_event: asyncio.Event | None = None
    worker_task: asyncio.Task[None] | None = None
    if settings.generation_worker_enabled and settings.app_env != "test":
        stop_event = asyncio.Event()
        worker_task = asyncio.create_task(
            run_worker(get_sessionmaker(), stop_event=stop_event),
            name="generation-worker",
        )
    try:
        yield
    finally:
        if stop_event is not None and worker_task is not None:
            stop_event.set()
            try:
                await asyncio.wait_for(
                    asyncio.shield(worker_task),
                    timeout=_WORKER_SHUTDOWN_TIMEOUT,
                )
            except TimeoutError:
                logger.warning("Generation worker did not stop within shutdown timeout")
                worker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await worker_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Generation worker exited during shutdown")


app = FastAPI(
    title="Mimik Suite API",
    version="0.1.0",
    description="Multi-tenant done-for-you creative-agency SaaS.",
    lifespan=lifespan,
)

app.include_router(tenants.router)
app.include_router(admin.router)
app.include_router(intake.router)
app.include_router(clients.router)
app.include_router(brands.router)
app.include_router(assets.router)
app.include_router(fonts.router)
app.include_router(pillars.router)
app.include_router(briefs.router)
app.include_router(jobs.router)
app.include_router(creatives.router)
app.include_router(creatives.artifact_router)
app.include_router(approvals.router)
app.include_router(ops.router)
app.include_router(tasks.router)
app.include_router(preferences.router)
app.include_router(billing.router)
app.include_router(invitations.router)
app.include_router(me.router)
app.include_router(portal.router)
app.include_router(deliveries.router)
app.include_router(exports.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
