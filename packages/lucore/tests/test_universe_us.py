"""US universe seed: ticker normalization + the S&P 500 CSV fallback when the Wikipedia
scrape is thin/broken."""
import pandas as pd


def test_rows_us_normalizes_tickers():
    from lucore.data.universe import _rows_us

    df = pd.DataFrame(
        [
            {"Symbol": "AAPL", "Security": "Apple"},
            {"Symbol": "BRK.B", "Security": "Berkshire Hathaway"},  # dot → dash
            {"Symbol": " nvda ", "Security": "NVIDIA"},             # trim + upper
            {"Symbol": "12€3", "Security": "junk"},                 # non-ascii → dropped
            {"Symbol": "", "Security": "empty"},                    # empty → dropped
        ]
    )
    out = _rows_us(df, "Symbol", "Security")
    syms = [s for s, _ in out]
    assert syms == ["AAPL", "BRK-B", "NVDA"]
    assert ("BRK-B", "Berkshire Hathaway") in out


def test_fetch_us_falls_back_to_csv(monkeypatch):
    """When the Wikipedia scrape yields too few rows, the CSV fallback is used."""
    from lucore.data import universe

    # Real maintained-CSV schema: Symbol,Security,GICS Sector,... (name col is `Security`).
    csv = "Symbol,Security,GICS Sector\n" + "\n".join(f"SYM{i},Co {i},Tech" for i in range(120))

    def fake_grab(url: str) -> str:
        if url == universe._SP500_URL:
            return "<html>no usable table</html>"
        if url == universe._SP500_CSV:
            return csv
        raise AssertionError(f"unexpected url {url}")

    # read_html on the junk HTML raises → fall through to CSV.
    monkeypatch.setattr(universe, "_grab", fake_grab)
    monkeypatch.setattr(universe.pd if hasattr(universe, "pd") else pd, "read_html",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("no tables")))
    # Ensure pandas.read_html is patched at the source pandas module the function imports.
    import pandas as _pd
    monkeypatch.setattr(_pd, "read_html", lambda *a, **k: (_ for _ in ()).throw(ValueError("no tables")))

    out = universe._fetch_us("sp500")
    assert len(out) == 120
    assert out[0] == ("SYM0", "Co 0")  # ticker AND name survive the fallback


def test_fetch_us_prefers_wiki_when_healthy(monkeypatch):
    from lucore.data import universe
    import pandas as _pd

    wiki_df = pd.DataFrame([{"Symbol": f"W{i}", "Security": f"Co{i}"} for i in range(150)])
    monkeypatch.setattr(_pd, "read_html", lambda *a, **k: [wiki_df])
    monkeypatch.setattr(universe, "_grab", lambda url: "<html/>")

    out = universe._fetch_us("sp500")
    assert len(out) == 150 and out[0][0] == "W0"  # used wiki, did not hit CSV
