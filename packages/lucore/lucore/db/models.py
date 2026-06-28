"""Core ORM models. Grows per phase; Phase 0/1 establishes the foundation.

Discipline: deterministic numbers live in compute-fed columns; AI write-backs
land in `analyses` (and later recommendations/briefings/...) as labeled opinion.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Stock(Base, TimestampMixin):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)  # canonical, e.g. NVDA, 0700.HK
    market: Mapped[str] = mapped_column(String(4), index=True)  # US / HK / CN
    name: Mapped[str | None] = mapped_column(String(256))
    exchange: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str | None] = mapped_column(String(8))

    items: Mapped[list["WatchlistItem"]] = relationship(back_populates="stock")


class PriceBar(Base):
    """Cached OHLCV. Daily bars are immutable history; intraday TTL'd by the cache layer."""
    __tablename__ = "price_bars"
    __table_args__ = (UniqueConstraint("symbol", "interval", "date", name="uq_pricebar"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), ForeignKey("stocks.symbol"), index=True)
    interval: Mapped[str] = mapped_column(String(8), default="1d")  # 1d/1wk/1mo/...
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base, TimestampMixin):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), ForeignKey("stocks.symbol"), index=True)
    tags: Mapped[str | None] = mapped_column(String(256))  # comma-separated for now
    note: Mapped[str | None] = mapped_column(Text)
    health_score: Mapped[float | None] = mapped_column(Float)

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")
    stock: Mapped[Stock] = relationship(back_populates="items")


class Analysis(Base, TimestampMixin):
    """An AI write-back: opinion produced by an LLM provider, never numbers it invented."""
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint("symbol", "kind", "idempotency_key", name="uq_analysis_idem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="research")  # research/news/portfolio/...
    summary: Mapped[str | None] = mapped_column(Text)
    structured_json: Mapped[str | None] = mapped_column(Text)  # JSON blob of the validated output
    provider: Mapped[str] = mapped_column(String(32), default="claude_code")
    idempotency_key: Mapped[str] = mapped_column(String(64), default="")  # e.g. source hash or date


class Portfolio(Base, TimestampMixin):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD")

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class Holding(Base, TimestampMixin):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "symbol", name="uq_holding"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), ForeignKey("stocks.symbol"), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_cost: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(32))  # csv / futu / manual

    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (UniqueConstraint("portfolio_id", "date", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    total_value: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct: Mapped[float | None] = mapped_column(Float)
    metrics_json: Mapped[str | None] = mapped_column(Text)
