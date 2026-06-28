"""Recommendation routes: list + generate per category."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lucore.compute.screener import CATEGORIES
from lucore.services import recommend as rec

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/categories")
def categories() -> list[str]:
    return CATEGORIES


@router.get("", response_model=list[rec.RecommendationOut])
def list_all(category: str | None = None) -> list[rec.RecommendationOut]:
    return rec.list_recommendations(category)


@router.post("/generate", response_model=list[rec.RecommendationOut])
def generate(category: str, top_n: int = 5) -> list[rec.RecommendationOut]:
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"unknown category; choose from {CATEGORIES}")
    try:
        return rec.generate(category, top_n=top_n)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"generation failed: {e}") from e
