"""LU MCP server (FastMCP).

The dual-brain seam: read tools return deterministic facts computed by lucore;
write-back tools persist the LLM's structured opinion into the local DB.
Phase 0 ships a health/read stub; tools grow each phase.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lucore import __version__
from lucore.config import get_settings
from lucore.db import init_db

mcp = FastMCP("limit-up")


@mcp.tool()
def lu_health() -> dict:
    """Return LU server status (version, db path, enabled markets, llm provider)."""
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "db": str(s.db_path),
        "llm_provider": s.llm_provider,
    }


def main() -> None:
    init_db()
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
