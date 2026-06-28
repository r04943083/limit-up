"""Unit tests for the company-profile adapter helpers (pure, no network)."""
from lucore.data.base import CompanyProfile, Dividend, HolderRow
from lucore.data.yfinance_adapter import _pct_str


def test_pct_str_parses_old_yfinance_format():
    assert _pct_str("12.34%") == 12.34 / 100.0
    assert _pct_str("0.50%") == 0.005
    assert _pct_str("100%") == 1.0


def test_pct_str_handles_garbage():
    assert _pct_str(None) is None
    assert _pct_str("n/a") is None
    assert _pct_str("") is None


def test_company_profile_defaults_are_empty():
    p = CompanyProfile(symbol="X", market="US")
    assert p.dividends == []
    assert p.top_institutions == []
    assert p.insiders_pct is None


def test_company_profile_round_trips_json():
    p = CompanyProfile(
        symbol="NVDA", market="US", name="NVIDIA", institutions_pct=0.7,
        dividends=[Dividend(ex_date="2026-06-04", amount=0.25)],
        top_institutions=[HolderRow(name="Blackrock", pct=0.08, shares=1.0, value=2.0)],
    )
    back = CompanyProfile.model_validate_json(p.model_dump_json())
    assert back.dividends[0].amount == 0.25
    assert back.top_institutions[0].name == "Blackrock"
    assert back.institutions_pct == 0.7
