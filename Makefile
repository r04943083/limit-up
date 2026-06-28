.PHONY: install api mcp web dev test lint initdb

# Install all Python workspace deps + web deps.
install:
	uv sync
	cd apps/web && npm install

# Run the local API (FastAPI) on :8000
api:
	uv run uvicorn luapi.main:app --reload --port 8000

# Run the MCP server (stdio) — usually launched by Claude / `claude -p`, not by hand.
mcp:
	uv run python -m lumcp.server

# Run the web app (Next.js) on :3000
web:
	cd apps/web && npm run dev

# Create / migrate the local SQLite DB.
initdb:
	uv run python scripts/init_db.py

# Run backend + frontend together.
dev:
	@echo "Starting API on :8000 and web on :3000 ..."
	@(uv run uvicorn luapi.main:app --reload --port 8000 &) ; cd apps/web && npm run dev

test:
	uv run pytest -q

lint:
	uv run ruff check .
