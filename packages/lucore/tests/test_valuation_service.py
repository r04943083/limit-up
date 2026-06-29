"""Valuation service wiring: quarterly statements + cached closes → PE/PB/PS bands +
analyst consensus. Dependencies are monkeypatched so the test needs no DB or network."""
import datetime as dt

from lucore.data.base import (
    Bar,
    Financials,
    Fundamentals,
    Quote,
    Statement,
    StatementRow,
)
from lucore.markets import Market
from lucore.services import valuation as vsvc
from lucore.services.research import ResearchBundle


def _stmt(label_to_values: dict[str, list[float | None]], periods: list[str]) -> Statement:
    return Statement(periods=periods, rows=[StatementRow(label=k, values=v)
                                            for k, v in label_to_values.items()])


def _fake_financials() -> Financials:
    # Quarterly, newest-first. 4 quarters of EPS=1.0 -> TTM EPS=4.0 at the newest quarter.
    qperiods = ["2024-12", "2024-09", "2024-06", "2024-03"]
    income_q = _stmt(
        {"摊薄EPS": [1.0, 1.0, 1.0, 1.0], "营业收入": [400.0, 400.0, 400.0, 400.0]},
        qperiods,
    )
    balance_q = _stmt({"股东权益": [1000.0, 1000.0, 1000.0, 1000.0]}, qperiods)
    return Financials(symbol="TEST", market=Market.US, currency="USD",
                      income_q=income_q, balance_q=balance_q, shares=100.0)


def _fake_bundle() -> ResearchBundle:
    fund = Fundamentals(
        symbol="TEST", market=Market.US, currency="USD",
        pe_ttm=12.0, pb=2.0, ps=1.5,
        recommendation="buy", recommendation_mean=2.0, num_analysts=20,
        target_mean=60.0, target_high=80.0, target_low=40.0, target_median=58.0,
    )
    quote = Quote(symbol="TEST", market=Market.US, price=50.0)
    return ResearchBundle(
        symbol="TEST", market="US", quote=quote, fundamentals=fund,
        technical_latest={}, technical_trend="flat", technical_signals=[], news=[],
        generated_at=dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc),
    )


def _fake_bars() -> list[Bar]:
    # Two closes after the only TTM-valid quarter end (2024-12-31): EPS=4 -> PE 12 then 13.
    return [
        Bar(date=dt.date(2025, 1, 2), open=48, high=49, low=47, close=48.0),
        Bar(date=dt.date(2025, 1, 3), open=52, high=53, low=51, close=52.0),
    ]


def _patch_extras(monkeypatch, dist=None, ind=None):
    """Stub the DB/network-backed extras (rating distribution + industry average)."""
    monkeypatch.setattr(vsvc, "_recommendation_distribution", lambda s: dist)
    monkeypatch.setattr(vsvc, "industry_average", lambda s: ind)


def test_get_valuation_builds_bands_and_consensus(monkeypatch):
    monkeypatch.setattr(vsvc, "get_research", lambda s: _fake_bundle())
    monkeypatch.setattr(vsvc, "get_financials_cached", lambda s: _fake_financials())
    monkeypatch.setattr(vsvc, "read_bars", lambda s, interval="1d": _fake_bars())
    from lucore.services.peers import IndustryMedian
    _patch_extras(
        monkeypatch,
        dist={"strong_buy": 6, "buy": 4, "hold": 2, "sell": 1, "strong_sell": 0},
        ind=IndustryMedian(industry="Software", n=12, pe=20.0, pb=5.0, ps=4.0),
    )

    v = vsvc.get_valuation("test")
    assert v.symbol == "TEST" and v.currency == "USD"

    # New 分析 fields: rating distribution + industry average + short interest.
    assert v.analyst.strong_buy == 6 and v.analyst.hold == 2
    assert v.industry == "Software"
    assert v.industry_avg.pe == 20.0 and v.industry_avg.peers == 12

    # PE: TTM EPS = 4.0 (4×1.0). closes 48,52 -> PE 12.0, 13.0. current overridden by fund.pe_ttm.
    assert [p.value for p in v.pe.points] == [12.0, 13.0]
    assert v.pe.current == 12.0          # from fundamentals, not last point
    assert v.pe.mean == 12.5 and v.pe.low == 12.0 and v.pe.high == 13.0

    # PB: BVPS = 1000/100 = 10. closes 48,52 -> PB 4.8, 5.2.
    assert [p.value for p in v.pb.points] == [4.8, 5.2]

    # PS: TTM revenue = 1600, /100 shares = SPS 16. closes 48,52 -> PS 3.0, 3.25.
    assert [p.value for p in v.ps.points] == [3.0, 3.25]

    # Analyst consensus + upside = (60-50)/50*100 = 20%.
    assert v.analyst.num_analysts == 20 and v.analyst.target_mean == 60.0
    assert abs(v.analyst.upside_pct - 20.0) < 1e-9


def test_get_valuation_handles_missing_statements(monkeypatch):
    empty = Financials(symbol="TEST", market=Market.US, currency="USD", shares=None)
    monkeypatch.setattr(vsvc, "get_research", lambda s: _fake_bundle())
    monkeypatch.setattr(vsvc, "get_financials_cached", lambda s: empty)
    monkeypatch.setattr(vsvc, "read_bars", lambda s, interval="1d": _fake_bars())
    _patch_extras(monkeypatch)  # no distribution, no industry average

    v = vsvc.get_valuation("test")
    # No statements -> empty bands, but current ratios still surface from fundamentals.
    assert v.pe.points == [] and v.pe.current == 12.0
    assert v.pb.points == [] and v.ps.points == []
    assert v.analyst.upside_pct is not None  # consensus independent of statements
