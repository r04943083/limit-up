"""Sentence-level red-line diff between two document sections (e.g. two years' 10-K Risk
Factors). Pure stdlib (difflib); unchanged runs collapse to an elision so only the material
changes surface. Deterministic — the LLM may later summarize the diff but never computes it.
"""
from __future__ import annotations

import difflib
import re

from pydantic import BaseModel

_SENT = re.compile(r"(?<=[.!?。!?])\s+")


def _split(text: str) -> list[str]:
    """Split into sentence units for a readable diff. Whitespace (incl. hard line-wraps) is
    collapsed FIRST so year-to-year reflowing of identical prose doesn't masquerade as changes —
    only real wording differences surface."""
    flat = re.sub(r"\s+", " ", text or "").strip()
    if not flat:
        return []
    return [s.strip() for s in _SENT.split(flat) if s.strip()]


class DiffChunk(BaseModel):
    op: str            # same | added | removed
    text: str


class TextDiff(BaseModel):
    chunks: list[DiffChunk] = []
    added_count: int = 0        # sentences added
    removed_count: int = 0      # sentences removed
    changed: bool = False


def diff_text(old: str, new: str, *, context: int = 1) -> TextDiff:
    """Red-line diff old→new. Equal runs longer than ``context`` sentences collapse to a single
    '… N 处未变 …' elision so the reader sees only what changed."""
    a, b = _split(old), _split(new)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    chunks: list[DiffChunk] = []
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            run = b[j1:j2]
            if len(run) <= context * 2:
                for s in run:
                    chunks.append(DiffChunk(op="same", text=s))
            else:  # keep a little context at each edge, elide the middle
                for s in run[:context]:
                    chunks.append(DiffChunk(op="same", text=s))
                chunks.append(DiffChunk(op="same", text=f"…（{len(run) - context * 2} 处未变）…"))
                # slice from an explicit index (run[-0:] would wrongly be the WHOLE run)
                for s in run[len(run) - context:]:
                    chunks.append(DiffChunk(op="same", text=s))
        else:
            if tag in ("delete", "replace"):
                for s in a[i1:i2]:
                    chunks.append(DiffChunk(op="removed", text=s))
                    removed += 1
            if tag in ("insert", "replace"):
                for s in b[j1:j2]:
                    chunks.append(DiffChunk(op="added", text=s))
                    added += 1
    return TextDiff(chunks=chunks, added_count=added, removed_count=removed,
                    changed=(added > 0 or removed > 0))
