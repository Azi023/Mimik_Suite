"""Mimik Suite API entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from api.routers import brands, briefs, clients, jobs, pillars, tenants

app = FastAPI(
    title="Mimik Suite API",
    version="0.1.0",
    description="Multi-tenant done-for-you creative-agency SaaS.",
)

app.include_router(tenants.router)
app.include_router(clients.router)
app.include_router(brands.router)
app.include_router(pillars.router)
app.include_router(briefs.router)
app.include_router(jobs.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
