# limit-up (LU)

An AI-native **personal** investment platform. LU researches, recommends, simulates,
manages, journals, and continuously improves investment decisions — with AI doing the
reasoning. Local-first, premium Webull-style dark UI, covering **US + HK + A-share**.

## Architecture — the "dual brain"

- **Python (`packages/lucore`)** is the deterministic compute engine: market data,
  indicators, screening, backtesting, portfolio/paper-trade math. It never asks an LLM
  to compute a number.
- **An LLM does the reasoning** via a pluggable `LLMProvider`. The default is **headless
  Claude Code (`claude -p`)** — zero marginal cost on a Max plan, seamless background
  generation. Optional paid providers: GLM-4.6, Anthropic API.
- **MCP server (`apps/mcp`)** exposes LU tools to Claude Desktop/Code/Cursor and to the
  headless brain. Read tools return facts; write-back tools persist the LLM's structured
  opinion into the local DB.
- **Web app (`apps/web`, Next.js)** displays stored results and drives generation.

```
Browser ──REST──> apps/api (FastAPI) ─┐
                                       ├─> packages/lucore ──> SQLite (data/lu.db)
Claude / claude -p ──MCP──> apps/mcp ─┘
```

## Quick start

```bash
make install      # uv sync + npm install
make initdb       # create data/lu.db
make api          # FastAPI on http://localhost:8000  (try /health)
make web          # Next.js on http://localhost:3000
make test         # pytest
```

Requires Python 3.12 (via `uv`) and Node 20+. Copy `.env.example` to `.env` to configure
(everything is optional — LU runs with zero config and zero AI cost).

## Status

Phase 0 — scaffolding. See the plan for the full phased roadmap.

> Not financial advice. AI outputs are labeled opinion.
