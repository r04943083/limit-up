"""LLM usage routes — token/cost burn so the user can watch their quota."""
from __future__ import annotations

from fastapi import APIRouter

from lucore.services.usage import UsageSummary, summary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummary)
def usage_summary() -> UsageSummary:
    return summary()
