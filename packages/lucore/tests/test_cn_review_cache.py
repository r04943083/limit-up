"""涨停复盘 cache guard: a *failed* limit-up fetch (ok=False, count=0) must NOT be persisted
as an empty 'no data' review — that would poison the day's cache and be served forever."""
import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LU_DATA_DIR", str(tmp_path))
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    import lucore.db.session as session_mod

    session_mod._engine = None
    session_mod._SessionLocal = None
    from lucore.db import init_db

    init_db()
    yield


def test_failed_fetch_is_not_cached(db, monkeypatch):
    from lucore.services import cn_review

    # Simulate gather_facts seeing a throttled akshare: fetch failed, zero rows.
    monkeypatch.setattr(cn_review, "gather_facts",
                        lambda date: {"_pool_ok": False, "zt_count": 0, "date": date})

    out = cn_review.compute_zt_review("20260101")
    assert out.provider == "cache-miss"                 # ephemeral, not a real review
    assert cn_review.latest_zt_review("20260101") is None  # nothing persisted → recomputable


def test_genuine_empty_day_is_cached(db, monkeypatch):
    from lucore.services import cn_review

    # A real non-trading day: fetch succeeded, legitimately zero limit-ups.
    monkeypatch.setattr(cn_review, "gather_facts",
                        lambda date: {"_pool_ok": True, "zt_count": 0, "date": date})

    out = cn_review.compute_zt_review("20260101")
    assert out.provider != "cache-miss"
    assert out.result.sentiment == "该日无涨停数据"
    assert cn_review.latest_zt_review("20260101") is not None  # persisted (won't recompute)
