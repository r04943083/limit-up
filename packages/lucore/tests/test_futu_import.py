"""Futu .ebk parsing — pin symbol normalization and non-equity skipping."""
from lucore.services.futu_import import parse_ebk, to_futu_line


def _by_raw(rows):
    return {r.raw: r for r in rows}


def test_export_reverses_import():
    # to_futu_line is the inverse of _parse_line for supported equities.
    assert to_futu_line("NVDA") == "31#NVDA"
    assert to_futu_line("BRK-B") == "31#BRK.B"
    assert to_futu_line("0700.HK") == "74#00700"
    assert to_futu_line("9988.HK") == "74#09988"
    assert to_futu_line("600519.SS") == "1600519"
    assert to_futu_line("002645.SZ") == "0002645"
    # Round-trip: parse(export(x)) == x for each market.
    for sym in ["NVDA", "BRK-B", "0700.HK", "600519.SS", "002645.SZ"]:
        line = to_futu_line(sym)
        assert line is not None
        assert parse_ebk(line)[0].symbol == sym


def test_normalizes_us_hk_a_share():
    text = "\n".join([
        "31#NVDA",      # US
        "31#BRK.B",     # US class share -> BRK-B
        "74#00700",     # HK -> 0700.HK
        "74#09988",     # HK -> 9988.HK
        "1688347",      # SH STAR -> 688347.SS
        "1600519",      # SH main -> 600519.SS
        "0002645",      # SZ -> 002645.SZ
        "0300750",      # SZ ChiNext -> 300750.SZ
    ])
    rows = _by_raw(parse_ebk(text))
    assert rows["31#NVDA"].symbol == "NVDA" and rows["31#NVDA"].market == "US"
    assert rows["31#BRK.B"].symbol == "BRK-B"
    assert rows["74#00700"].symbol == "0700.HK" and rows["74#00700"].market == "HK"
    assert rows["74#09988"].symbol == "9988.HK"
    assert rows["1688347"].symbol == "688347.SS" and rows["1688347"].market == "CN"
    assert rows["1600519"].symbol == "600519.SS"
    assert rows["0002645"].symbol == "002645.SZ"
    assert rows["0300750"].symbol == "300750.SZ"
    assert all(r.kind == "equity" for r in rows.values())


def test_skips_non_equities():
    text = "\n".join([
        "31#.SPX",          # index
        "31#ESmain",        # future
        "31#LIST23492",     # Futu list ref
        "BD#US20Y",         # bond
        "AU#CETF",          # foreign
        "2USDindex",        # forex
        "1000001",          # SH index (上证指数)
    ])
    rows = parse_ebk(text)
    assert all(r.symbol is None for r in rows)
    kinds = {r.raw: r.kind for r in rows}
    assert kinds["31#.SPX"] == "index"
    assert kinds["31#ESmain"] == "future"
    assert kinds["31#LIST23492"] == "list"
    assert kinds["BD#US20Y"] == "bond"
    assert kinds["AU#CETF"] == "foreign"
    assert kinds["1000001"] == "index"


def test_handles_bom_and_blank_lines():
    rows = parse_ebk("﻿31#AAPL\r\n\r\n74#02007\r\n")
    syms = [r.symbol for r in rows if r.symbol]
    assert syms == ["AAPL", "2007.HK"]
