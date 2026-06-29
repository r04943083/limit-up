"""Price-bar cache: idempotent writes (ON CONFLICT DO NOTHING) and ordered reads. No network."""
import datetime as dt

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
    from lucore.data import cache

    init_db()
    cache.ensure_stock("TST")  # satisfy the price_bars -> stocks FK
    yield cache


def _bars(n: int, *, close: float = 1.5):
    from lucore.data.base import Bar

    base = dt.date(2024, 1, 1)
    return [
        Bar(date=base + dt.timedelta(days=i), open=1, high=2, low=0.5, close=close, volume=100)
        for i in range(n)
    ]


def test_write_bars_is_idempotent_and_dedupes_batch(db):
    bars = _bars(5)
    bars.append(_bars(5)[2])  # duplicate date within the same batch
    assert db.write_bars("TST", "1d", bars) == 5  # batch deduped, 5 unique dates
    assert db.write_bars("TST", "1d", bars) == 0  # re-insert: all conflict -> nothing written
    rows = db.read_bars("TST", "1d")
    assert len(rows) == 5
    assert [r.date for r in rows] == sorted(r.date for r in rows)  # read returns ordered
    assert db.latest_cached_date("TST", "1d") == dt.date(2024, 1, 5)


def test_write_bars_empty_is_noop(db):
    assert db.write_bars("TST", "1d", []) == 0
    assert db.read_bars("TST", "1d") == []
