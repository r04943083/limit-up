"""SEC EDGAR insider (Form 4) aggregation + cluster-buy signal, and cache-first service
behavior (US-only, degrade on failure). EDGAR network is faked."""
import datetime as dt

import pytest


# ---- Fakes mimicking the edgartools object graph ----
class _Act:
    def __init__(self, code, shares, price=None, value=None, date=None,
                 ttype="", security="Common Stock"):
        self.code = code
        self.shares = shares
        self.price_per_share = price
        self.value = value
        self.transaction_date = date
        self.transaction_type = ttype
        self.security_title = security


class _Form4:
    def __init__(self, insider, position, period, acts):
        self.insider_name = insider
        self.position = position
        self.reporting_period = period
        self._acts = acts

    def get_transaction_activities(self):
        return self._acts


class _Filing:
    def __init__(self, form4):
        self._f = form4

    def obj(self):
        return self._f


class _Filings:
    def __init__(self, rows):
        self._rows = rows

    def head(self, n):
        return self._rows[:n]


class _Company:
    last_symbol = None

    def __init__(self, symbol):
        _Company.last_symbol = symbol
        self.name = "Fake Co"

    def get_filings(self, form=None):
        today = dt.date.today().isoformat()
        old = (dt.date.today() - dt.timedelta(days=200)).isoformat()
        return _Filings([
            _Filing(_Form4("Alice", "CEO", today, [_Act("P", 1000, 10.0, 10000, today)])),
            _Filing(_Form4("Bob", "CFO", today, [_Act("P", 500, 11.0, 5500, today)])),
            _Filing(_Form4("Cara", "Director", today, [_Act("S", 300, 12.0, 3600, today)])),
            # An old purchase OUTSIDE the 90-day window must not count toward the signal.
            _Filing(_Form4("Dan", "10% owner", old, [_Act("P", 9999, 9.0, 0, old)])),
        ])


@pytest.fixture()
def fake_edgar(monkeypatch):
    monkeypatch.setattr("edgar.set_identity", lambda *a, **k: None)
    monkeypatch.setattr("edgar.Company", _Company)
    import lucore.data.edgar as ed
    ed._identity_set = False
    yield ed


def test_cluster_buy_and_tallies(fake_edgar):
    rep = fake_edgar.fetch_insider_report("AAPL", filings=20, window_days=90)
    assert rep.symbol == "AAPL"
    assert rep.buy_count == 2          # Alice + Bob open-market buys in window (Dan's is old)
    assert rep.sell_count == 1         # Cara
    assert rep.distinct_buyers == 2
    assert rep.distinct_sellers == 1
    assert rep.cluster_buy is True     # ≥2 distinct buyers → signal
    assert rep.net_shares == 1000 + 500 - 300  # Σ P − Σ S over the window
    # Every parsed transaction is surfaced (incl. the out-of-window one), newest first-ish.
    assert len(rep.transactions) == 4


def test_no_cluster_with_single_buyer(monkeypatch):
    today = dt.date.today().isoformat()

    class _One(_Company):
        def get_filings(self, form=None):
            return _Filings([_Filing(_Form4("Solo", "CEO", today, [_Act("P", 100, 5.0, 500, today)]))])

    monkeypatch.setattr("edgar.set_identity", lambda *a, **k: None)
    monkeypatch.setattr("edgar.Company", _One)
    import lucore.data.edgar as ed
    ed._identity_set = False
    rep = ed.fetch_insider_report("MSFT")
    assert rep.distinct_buyers == 1 and rep.cluster_buy is False


# ---- Service: cache-first + US-only ----
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


def test_service_non_us_returns_empty_without_fetch(db, monkeypatch):
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    def boom(*a, **k):
        raise AssertionError("should not fetch for non-US")

    monkeypatch.setattr(ed, "fetch_insider_report", boom)
    r = edgar_svc.get_insider_report("0700.HK")
    assert r.ok and r.report.symbol == "0700.HK" and r.report.buy_count == 0


def test_service_cache_first_and_degrade(db, monkeypatch):
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    calls = {"n": 0}

    def fake(sym, **k):
        calls["n"] += 1
        return ed.InsiderReport(symbol=sym, buy_count=3, distinct_buyers=2, cluster_buy=True)

    monkeypatch.setattr(ed, "fetch_insider_report", fake)
    r1 = edgar_svc.get_insider_report("AAPL")
    assert r1.ok and r1.report.cluster_buy and calls["n"] == 1
    r2 = edgar_svc.get_insider_report("AAPL")           # served from cache
    assert r2.ok and calls["n"] == 1

    # Expire cache + make source fail → serve stale, ok=False.
    monkeypatch.setattr(edgar_svc.mc, "fresh_enough", lambda *a, **k: False)
    monkeypatch.setattr(ed, "fetch_insider_report",
                        lambda s, **k: (_ for _ in ()).throw(RuntimeError("edgar down")))
    r3 = edgar_svc.get_insider_report("AAPL")
    assert r3.ok is False and r3.report.cluster_buy and "edgar down" in r3.error


def test_filing_diff_service(db, monkeypatch):
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    secs = [
        ed.FilingSection(date="2026-01-01", form="10-K",
                         text="We face competition. Supply is stable. Margins are healthy."),
        ed.FilingSection(date="2025-01-01", form="10-K",
                         text="We face competition. Supply is stable. Costs are rising."),
    ]  # newest-first
    monkeypatch.setattr(ed, "fetch_sections", lambda s, **k: secs)

    r = edgar_svc.get_filing_diff("AAPL", form="10-K", section="risk_factors")
    assert r.ok and r.new_date == "2026-01-01" and r.old_date == "2025-01-01"
    assert r.section_label == "风险因素"
    assert r.diff.changed and r.diff.added_count >= 1 and r.diff.removed_count >= 1
    added = " ".join(c.text for c in r.diff.chunks if c.op == "added")
    assert "Margins" in added

    # Second call served from cache (fetch_sections not called again).
    monkeypatch.setattr(ed, "fetch_sections", lambda s, **k: (_ for _ in ()).throw(RuntimeError("x")))
    r2 = edgar_svc.get_filing_diff("AAPL", form="10-K", section="risk_factors")
    assert r2.ok and r2.new_date == "2026-01-01"


def test_filing_diff_degenerate_is_cached(db, monkeypatch):
    """A can't-diff result (one filing) is cached so repeated clicks don't re-parse."""
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    calls = {"n": 0}

    def one_filing(s, **k):
        calls["n"] += 1
        return [ed.FilingSection(date="2026-01-01", form="10-K", text="Only one.")]

    monkeypatch.setattr(ed, "fetch_sections", one_filing)
    r1 = edgar_svc.get_filing_diff("AAPL", section="risk_factors")
    assert r1.ok is False and calls["n"] == 1
    r2 = edgar_svc.get_filing_diff("AAPL", section="risk_factors")
    assert r2.ok is False and calls["n"] == 1  # served from cache, not re-parsed


def test_filing_diff_stale_on_error_flags_not_ok(db, monkeypatch):
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    secs = [ed.FilingSection(date="2026-01-01", form="10-K", text="A. B new."),
            ed.FilingSection(date="2025-01-01", form="10-K", text="A. B old.")]
    monkeypatch.setattr(ed, "fetch_sections", lambda s, **k: secs)
    assert edgar_svc.get_filing_diff("AAPL", section="business").ok is True

    # Expire cache + fail the fetch → serve stale content but with ok=False + error.
    monkeypatch.setattr(edgar_svc.mc, "fresh_enough", lambda *a, **k: False)
    monkeypatch.setattr(ed, "fetch_sections", lambda s, **k: (_ for _ in ()).throw(RuntimeError("edgar down")))
    r = edgar_svc.get_filing_diff("AAPL", section="business")
    assert r.ok is False and "edgar down" in r.error and r.new_date == "2026-01-01"  # stale content served


def test_filing_diff_non_us_empty(db, monkeypatch):
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    monkeypatch.setattr(ed, "fetch_sections", lambda s, **k: (_ for _ in ()).throw(AssertionError("no fetch")))
    r = edgar_svc.get_filing_diff("0700.HK")
    assert r.ok and r.diff.changed is False


def test_filings_service_roundtrip(db, monkeypatch):
    from lucore.data import edgar as ed
    from lucore.services import edgar_svc

    rows = [ed.FilingRow(form="10-Q", date="2026-05-01", title="Quarterly", url="u", accession="a"),
            ed.FilingRow(form="8-K", date="2026-04-01")]
    monkeypatch.setattr(ed, "fetch_recent_filings", lambda s, **k: rows)
    r1 = edgar_svc.get_filings("AAPL")
    assert r1.ok and len(r1.filings) == 2 and r1.filings[0].form == "10-Q"
    r2 = edgar_svc.get_filings("AAPL")  # from cache
    assert [f.form for f in r2.filings] == ["10-Q", "8-K"]
