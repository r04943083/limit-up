"""Unit tests for the AI 涨停复盘 models / helpers (pure, no network, no LLM)."""
from lucore.services.cn_review import SavedZtReview, ZtReviewResult, _yi
import datetime as dt


def test_yi_converts_to_100m_units():
    assert _yi(634_000_000) == 6.34   # 6.34 亿
    assert _yi(None) is None
    assert _yi(0) == 0.0


def test_review_result_defaults_empty():
    r = ZtReviewResult()
    assert r.leaders == [] and r.risks == []
    assert r.sentiment == ""


def test_saved_review_roundtrips_json():
    saved = SavedZtReview(
        date="20260628", provider="claude_code",
        created_at=dt.datetime(2026, 6, 28, tzinfo=dt.timezone.utc),
        result=ZtReviewResult(sentiment="情绪偏暖", leaders=["兴业科技"]),
        facts={"zt_count": 60, "max_boards": 6},
    )
    back = SavedZtReview.model_validate_json(saved.model_dump_json())
    assert back.result.leaders == ["兴业科技"]
    assert back.facts["max_boards"] == 6
