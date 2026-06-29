"""AI 对话 (#1).

A conversational assistant grounded in LU's deterministic data. When the user mentions
tickers, LU injects the cached research facts so the model reasons over real numbers
(dual-brain: never invent figures). History is persisted per session in `chat_messages`.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from pydantic import BaseModel
from sqlalchemy import select

from ..db import session_scope
from ..db.models import ChatMessage
from ..llm.base import LLMProvider, get_provider, with_chinese
from . import usage
from .analyze import _facts
from .research import get_research

_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z]{2})?|\d{4,6}\.[A-Z]{2})\b")
_STOP = {"AI", "US", "HK", "CN", "DCF", "PE", "PB", "PS", "ROE", "RSI", "MACD", "ETF", "IPO", "GDP", "CEO"}

SYSTEM = (
    "You are LU's investing copilot. You help the user research and reason about markets. When the "
    "user references a ticker, LU gives you that symbol's FACTS (price, fundamentals, technicals, "
    "news) — treat those numbers as ground truth and never invent figures. Be concise, balanced and "
    "practical. End material claims with a brief '· 非投资建议' style caveat when giving a view."
)


class ChatTurn(BaseModel):
    id: int
    role: str
    content: str
    created_at: dt.datetime


class ChatReply(BaseModel):
    reply: str
    provider: str
    symbols_used: list[str] = []


def history(session_id: str = "default", limit: int = 50) -> list[ChatTurn]:
    with session_scope() as s:
        rows = list(
            s.execute(
                select(ChatMessage).where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).limit(limit)
            ).scalars()
        )
        return [ChatTurn(id=r.id, role=r.role, content=r.content, created_at=r.created_at) for r in rows]


def clear(session_id: str = "default") -> int:
    with session_scope() as s:
        rows = list(s.execute(select(ChatMessage).where(ChatMessage.session_id == session_id)).scalars())
        for r in rows:
            s.delete(r)
        return len(rows)


def _extract_symbols(text: str) -> list[str]:
    out: list[str] = []
    for m in _TICKER_RE.findall(text or ""):
        sym = m.upper()
        if sym in _STOP or sym in out:
            continue
        out.append(sym)
    return out[:3]


def _ground(symbols: list[str]) -> tuple[str, list[str]]:
    used: list[str] = []
    blocks: list[dict] = []
    for sym in symbols:
        try:
            blocks.append(_facts(get_research(sym, cached=True)))
            used.append(sym)
        except Exception:  # noqa: BLE001
            continue
    if not blocks:
        return "", used
    return "FACTS (ground truth):\n" + json.dumps(blocks, indent=2, default=str, ensure_ascii=False), used


def send(message: str, *, session_id: str = "default", provider: LLMProvider | None = None) -> ChatReply:
    message = (message or "").strip()
    if not message:
        raise ValueError("empty message")
    provider = provider or get_provider()

    past = history(session_id, limit=12)
    facts_block, used = _ground(_extract_symbols(message))
    convo = "\n".join(f"{'用户' if t.role == 'user' else '助手'}: {t.content}" for t in past[-8:])
    prompt = (
        (f"对话历史:\n{convo}\n\n" if convo else "")
        + (facts_block + "\n\n" if facts_block else "")
        + f"用户: {message}\n\n助手:"
    )
    reply = provider.complete(prompt, system=with_chinese(SYSTEM)).strip()
    usage.record(provider, "chat", used[0] if used else None)

    with session_scope() as s:
        s.add(ChatMessage(session_id=session_id, role="user", content=message))
        s.add(ChatMessage(session_id=session_id, role="assistant", content=reply, provider=provider.name))
    return ChatReply(reply=reply, provider=provider.name, symbols_used=used)
