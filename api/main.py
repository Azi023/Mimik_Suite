"""Mimik Suite API entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

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

app = FastAPI(
    title="Mimik Suite API",
    version="0.1.0",
    description="Multi-tenant done-for-you creative-agency SaaS.",
)

app.include_router(tenants.router)
app.include_router(admin.router)
app.include_router(intake.router)
app.include_router(clients.router)
app.include_router(brands.router)
app.include_router(assets.router)
app.include_router(pillars.router)
app.include_router(briefs.router)
app.include_router(jobs.router)
app.include_router(creatives.router)
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
