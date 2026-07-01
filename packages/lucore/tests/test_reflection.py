"""Decision-reflection memory: log decisions (idempotent per day) + grade realized outcomes."""
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

    init_db()
    yield


def _snap(symbol, price):
    from lucore.data.base import Fundamentals, Quote
    from lucore.services.research import ResearchBundle, save_snapshot

    save_snapshot(ResearchBundle(
        symbol=symbol, market="US",
        quote=Quote(symbol=symbol, market="US", price=price),
        fundamentals=Fundamentals(symbol=symbol, market="US"),
        technical_latest={}, technical_trend="up", technical_signals=[], news=[], spark=[],
        generated_at=dt.datetime.now(dt.timezone.utc),
    ))


def test_log_decision_idempotent_per_day(db):
    from lucore.db import session_scope
    from lucore.db.models import AgentDecision
    from lucore.services.reflection import log_decision
    from sqlalchemy import func, select

    day = dt.date(2025, 1, 1)
    log_decision("NVDA", kind="council", action="buy", stance="bullish", score=8.0, price=100.0, today=day)
    log_decision("NVDA", kind="council", action="add", stance="bullish", score=7.0, price=101.0, today=day)
    with session_scope() as s:
        n = s.execute(select(func.count()).select_from(AgentDecision)
                      .where(AgentDecision.symbol == "NVDA")).scalar()
        row = s.execute(select(AgentDecision).where(AgentDecision.symbol == "NVDA")).scalar_one()
    assert n == 1                    # same symbol+kind+day upserts, not duplicates
    # The call updates to the latest (action=add), but the decision PRICE is anchored to the
    # first decision of the day (100.0), so reflection grades against a stable entry price.
    assert row.action == "add" and row.price == 100.0


def test_grading_hit_miss_open_na(db):
    from lucore.services.reflection import get_reflections, log_decision

    _snap("WIN", 110.0)   # long call, price rose → hit
    _snap("LOSE", 90.0)   # long call, price fell → miss
    _snap("HOLD", 105.0)  # hold → no directional call → open
    # NOPRICE has no snapshot → current price None → na

    log_decision("WIN", kind="council", action="buy", stance="bullish", score=8.0, price=100.0)
    log_decision("LOSE", kind="council", action="buy", stance="bullish", score=7.0, price=100.0)
    log_decision("HOLD", kind="council", action="hold", stance="neutral", score=5.0, price=100.0)
    log_decision("NOPRICE", kind="council", action="sell", stance="bearish", score=4.0, price=100.0)

    summ = get_reflections()
    by = {r.symbol: r for r in summ.rows}
    assert by["WIN"].grade == "hit" and by["WIN"].return_pct == 10.0
    assert by["LOSE"].grade == "miss" and by["LOSE"].return_pct == -10.0
    assert by["HOLD"].grade == "open"
    assert by["NOPRICE"].grade == "na"
    # Two graded (WIN hit, LOSE miss) → 50% hit rate; avg realized over the two = 0%.
    assert summ.graded == 2 and summ.hits == 1 and summ.hit_rate_pct == 50.0
    assert summ.avg_return_pct == 0.0


def test_flat_move_is_open_not_miss(db):
    """A just-made directional call whose price hasn't moved yet grades 'open', not 'miss'."""
    from lucore.services.reflection import get_reflections, log_decision

    _snap("FLAT", 100.0)  # current == decision price → no realized move
    log_decision("FLAT", kind="council", action="buy", stance="bullish", score=8.0, price=100.0)
    summ = get_reflections()
    row = next(r for r in summ.rows if r.symbol == "FLAT")
    assert row.return_pct == 0.0 and row.grade == "open"
    assert summ.graded == 0 and summ.hit_rate_pct is None  # not counted as a miss


def test_avg_return_is_pnl_style_for_shorts(db):
    """A correct SHORT (price fell) contributes POSITIVELY to the P&L-style average."""
    from lucore.services.reflection import get_reflections, log_decision

    _snap("SHRT", 80.0)  # sell @100 → -20% price, +20% P&L
    log_decision("SHRT", kind="council", action="sell", stance="bearish", score=3.0, price=100.0)
    summ = get_reflections()
    assert summ.hits == 1 and summ.hit_rate_pct == 100.0
    assert summ.avg_return_pct == 20.0  # short profit, not −20


def test_short_call_grading(db):
    from lucore.services.reflection import get_reflections, log_decision

    _snap("DROP", 80.0)  # sell call, price fell → hit
    log_decision("DROP", kind="council", action="sell", stance="bearish", score=3.0, price=100.0)
    r = next(x for x in get_reflections().rows if x.symbol == "DROP")
    assert r.grade == "hit" and r.return_pct == -20.0
