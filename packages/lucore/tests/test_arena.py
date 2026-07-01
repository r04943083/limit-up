"""AI arena: pure perf metrics + ledger→equity-curve reconstruction. No network, no LLM."""
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


def test_series_metrics_basic():
    from lucore.compute.perf import series_metrics

    m = series_metrics([100.0, 110.0, 99.0, 121.0], 100.0)
    assert m.total_return_pct == 21.0  # 121/100 - 1
    # peak 110 -> trough 99 = 10% drawdown
    assert m.max_drawdown_pct == pytest.approx(10.0, abs=0.01)
    assert m.sharpe is not None
    assert m.worst_day_pct is not None and m.worst_day_pct < 0


def test_series_metrics_empty():
    from lucore.compute.perf import series_metrics

    assert series_metrics([], 100.0).total_return_pct is None
    assert series_metrics([100.0], 0.0).total_return_pct is None


def test_equity_curve_marks_to_cached_closes(db):
    from lucore.data import cache
    from lucore.data.base import Bar
    from lucore.db import session_scope
    from lucore.db.models import PaperAccount, PaperTrade
    from lucore.services import arena

    cache.ensure_stock("AAA")
    # closes 11..15 over 5 days
    cache.write_bars("AAA", "1d", [
        Bar(date=dt.date(2024, 1, d), open=10, high=10, low=10, close=10 + d, volume=1)
        for d in range(1, 6)
    ])
    with session_scope() as s:
        acct = PaperAccount(name="t", cash=100000.0, starting_cash=100000.0, kind="ai", persona="buffett")
        s.add(acct)
        s.flush()
        aid = acct.id
        # buy 100 @ 11 on day 1 -> cash 98900, mv tracks the close
        s.add(PaperTrade(account_id=aid, symbol="AAA", side="buy", quantity=100, price=11,
                         created_at=dt.datetime(2024, 1, 1, 10, 0)))

    master = [dt.date(2024, 1, d) for d in range(1, 6)]
    curve = arena.equity_curve(aid, master)
    eqs = {d: e for d, e in curve}
    # day1 close 11 -> equity 98900 + 1100 = 100000 ; day5 close 15 -> 98900 + 1500 = 100400
    assert eqs[dt.date(2024, 1, 1)] == 100000.0
    assert eqs[dt.date(2024, 1, 5)] == 100400.0


def test_equity_curve_falls_back_to_snapshot_price_when_no_bars(db):
    """A symbol with a snapshot price but NO cached daily bars must be valued at the snapshot
    price, not 0 — otherwise a fully-deployed AI account shows ≈ −100% and misranks."""
    import datetime as dt

    from lucore.data.base import Fundamentals, Quote
    from lucore.db import session_scope
    from lucore.db.models import PaperAccount, PaperTrade
    from lucore.services import arena
    from lucore.services.research import ResearchBundle, save_snapshot

    # Snapshot with a price, but we deliberately write NO PriceBar rows for BBB.
    save_snapshot(ResearchBundle(
        symbol="BBB", market="US",
        quote=Quote(symbol="BBB", market="US", price=25.0, currency="USD", name="B Co"),
        fundamentals=Fundamentals(symbol="BBB", market="US", name="B Co", currency="USD"),
        technical_latest={}, technical_trend="flat", technical_signals=[], news=[], spark=[],
        generated_at=dt.datetime.now(dt.timezone.utc),
    ))
    with session_scope() as s:
        acct = PaperAccount(name="t2", cash=100000.0, starting_cash=100000.0, kind="ai", persona="lynch")
        s.add(acct)
        s.flush()
        aid = acct.id
        # Deploy nearly all cash into BBB: 1000 @ 20 -> cash 80000, 1000 shares.
        s.add(PaperTrade(account_id=aid, symbol="BBB", side="buy", quantity=1000, price=20,
                         created_at=dt.datetime(2024, 1, 1, 10, 0)))

    master = [dt.date(2024, 1, d) for d in range(1, 4)]
    curve = arena.equity_curve(aid, master)
    eqs = {d: e for d, e in curve}
    # Without the fallback this collapses to cash (80000); with it: 80000 + 1000*25 = 105000.
    assert eqs[dt.date(2024, 1, 1)] == 105000.0


def test_equity_curve_empty_without_trades(db):
    from lucore.db import session_scope
    from lucore.db.models import PaperAccount
    from lucore.services import arena

    with session_scope() as s:
        acct = PaperAccount(name="t2", cash=100000.0, starting_cash=100000.0, kind="ai", persona="lynch")
        s.add(acct)
        s.flush()
        aid = acct.id
    assert arena.equity_curve(aid, [dt.date(2024, 1, 1)]) == []


class _FakeProvider:
    name = "fake"

    def __init__(self, targets, commentary="c"):
        self._out = {"targets": targets, "commentary": commentary}

    def generate_json(self, prompt, system=None):
        return self._out


def _ai_account(persona: str):
    from lucore.db import session_scope
    from lucore.db.models import PaperAccount

    with session_scope() as s:
        a = PaperAccount(name=f"AI·{persona}", cash=100000.0, starting_cash=100000.0,
                         kind="ai", persona=persona)
        s.add(a)
        s.flush()
        return a.id


def test_rebalance_caps_position_and_holds_cash(db, monkeypatch):
    from lucore.services import arena

    aid = _ai_account("buffett")  # value style → max_pos 0.22
    monkeypatch.setattr(arena, "_cache_price", lambda sym: 100.0)
    monkeypatch.setattr(arena, "_market_regime", lambda: "震荡")
    facts = [{"symbol": "AAA"}, {"symbol": "BBB"}]
    # AI asks for 90% in AAA + 10% in BBB. Cap clamps AAA to 22%; total deployed = 32%.
    res = arena.rebalance_account(aid, facts, _FakeProvider(
        [{"symbol": "AAA", "weight": 0.9, "reason": "x"}, {"symbol": "BBB", "weight": 0.1, "reason": "y"}]
    ))
    assert res.error is None
    assert res.target_invested_pct == 32.0  # 0.22 + 0.10, NOT forced to ~98%
    cash, _starting, _trades, held = arena._book(aid)
    assert abs(held["AAA"]["qty"] * 100 - 22000) < 600  # AAA ≈ 22% of 100k equity
    assert cash > 60000  # the rest is genuinely held as cash


def test_get_arena_exposes_trade_ledger(db):
    """The leaderboard surfaces each AI's full operation ledger (newest first) with
    time / side / price / qty / reason so the user can audit every decision."""
    from lucore.data import cache
    from lucore.data.base import Bar
    from lucore.db import session_scope
    from lucore.db.models import PaperTrade
    from lucore.services import arena

    cache.ensure_stock("AAA")
    cache.write_bars("AAA", "1d", [
        Bar(date=dt.date(2024, 1, d), open=10, high=10, low=10, close=10 + d, volume=1)
        for d in range(1, 6)
    ])
    aid = arena.ensure_arena(["buffett"])[0]
    with session_scope() as s:
        s.add(PaperTrade(account_id=aid, symbol="AAA", side="buy", quantity=100, price=11,
                         note="便宜", created_at=dt.datetime(2024, 1, 1, 10, 0)))
        s.add(PaperTrade(account_id=aid, symbol="AAA", side="sell", quantity=40, price=13,
                         note="止盈", created_at=dt.datetime(2024, 1, 3, 10, 0)))

    out = arena.get_arena(["buffett"])
    agent = next(a for a in out.agents if a.persona == "buffett")
    assert agent.trades_count == 2
    assert len(agent.trades) == 2
    assert agent.trades[0].side == "sell" and agent.trades[0].reason == "止盈"  # newest first
    assert agent.trades[0].at == dt.datetime(2024, 1, 3, 10, 0)
    assert agent.trades[1].side == "buy" and agent.trades[1].amount == pytest.approx(1100.0)


def test_rebalance_empty_targets_goes_to_cash(db, monkeypatch):
    from lucore.services import arena

    aid = _ai_account("wood")
    monkeypatch.setattr(arena, "_cache_price", lambda sym: 50.0)
    monkeypatch.setattr(arena, "_market_regime", lambda: "下行")
    res = arena.rebalance_account(aid, [{"symbol": "AAA"}], _FakeProvider([], commentary="空仓避险"))
    assert res.error is None
    assert res.target_invested_pct == 0.0
    cash, _starting, _trades, held = arena._book(aid)
    assert held == {}
    assert cash == 100000.0  # fully in cash
