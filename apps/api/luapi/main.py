"""FastAPI entrypoint for the LU local web app.

Thin adapter: routes call into lucore services. Boots the local SQLite DB on startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lucore import __version__
from lucore.config import get_settings
from lucore.db import init_db
from lucore.scheduler.jobs import shutdown_scheduler, start_scheduler

from .routers import (
    arena,
    briefing,
    chat,
    cn,
    journal,
    markets,
    paper,
    portfolio,
    recommendations,
    stocks,
    strategy,
    studio,
    sync,
    usage,
    watchlists,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title="limit-up (LU) API", version=__version__, lifespan=lifespan)

# Local web app dev origins (Next.js).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stocks.router)
app.include_router(watchlists.router)
app.include_router(portfolio.router)
app.include_router(recommendations.router)
app.include_router(sync.router)
app.include_router(usage.router)
app.include_router(briefing.router)
app.include_router(markets.router)
app.include_router(cn.router)
app.include_router(journal.router)
app.include_router(paper.router)
app.include_router(arena.router)
app.include_router(strategy.router)
app.include_router(chat.router)
app.include_router(studio.router)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "db": str(settings.db_path),
        "llm_provider": settings.llm_provider,
        "markets": ["US"] + (["HK"] if settings.enable_hk else []) + (["CN"] if settings.enable_cn else []),
    }
