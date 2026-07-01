"""财经日历: event-date parsing, upcoming-window filter, and tracked-symbol aggregation."""
import datetime as dt

import pytest


def test_is_upcoming_window():
    from lucore.data.events import is_upcoming

    today = dt.date(2025, 6, 1)
    assert is_upcoming("2025-06-15", within_days=30, today=today) is True
    assert is_upcoming("2025-06-01", within_days=30, today=today) is True   # inclusive today
    assert is_upcoming("2025-05-31", within_days=30, today=today) is False  # past
    assert is_upcoming("2025-08-01", within_days=30, today=today) is False  # beyond window
    assert is_upcoming(None, within_days=30, today=today) is False
    assert is_upcoming("garbage", within_days=30, today=today) is False


def test_fetch_company_events_parses_calendar(monkeypatch):
    from lucore.data import events as ev

    class _T:
        def __init__(self, s): ...
        calendar = {
            "Earnings Date": [dt.date(2025, 7, 31)],
            "Ex-Dividend Date": dt.date(2025, 5, 11),
            "Dividend Date": dt.date(2025, 5, 14),
            "Earnings Average": 1.89, "Revenue Average": 1.08e11,
        }

    monkeypatch.setattr("yfinance.Ticker", _T)
    e = ev.fetch_company_events("AAPL")
    assert e.earnings_date == "2025-07-31"     # list → first
    assert e.ex_dividend_date == "2025-05-11"
    assert e.eps_avg == 1.89


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


def test_get_calendar_aggregates_and_sorts(db, monkeypatch):
    from lucore.data import events as ev
    from lucore.services import calendar_svc as cs

    monkeypatch.setattr(cs, "tracked_symbols", lambda: ["AAA", "BBB"])
    events = {
        "AAA": ev.CompanyEvents(symbol="AAA", earnings_date="2025-06-20", eps_avg=2.0,
                                ex_dividend_date="2025-06-10"),
        "BBB": ev.CompanyEvents(symbol="BBB", earnings_date="2025-07-30"),  # beyond 30d window
    }
    monkeypatch.setattr(cs, "get_company_events", lambda s, allow_fetch=True: events[s])

    res = cs.get_calendar(within_days=30, today=dt.date(2025, 6, 1))
    kinds = [(e.symbol, e.type) for e in res.events]
    # AAA earnings (6-20) + AAA ex-div (6-10) are in-window; BBB earnings (7-30) is not.
    assert ("AAA", "ex_dividend") in kinds and ("AAA", "earnings") in kinds
    assert ("BBB", "earnings") not in kinds
    # Sorted soonest-first: ex-div 6-10 before earnings 6-20.
    assert res.events[0].date == "2025-06-10"
    assert res.events[0].detail is None
    earnings = next(e for e in res.events if e.type == "earnings")
    assert "EPS 预期 2.00" in earnings.detail
