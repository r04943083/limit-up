"""yfinance adapter — covers US, HK (.HK) and A-share (.SS/.SZ) for Phase 1.

yfinance scrapes Yahoo and can rate-limit / break; everything here is defensive so a
missing field degrades to None rather than raising. Swap in Finnhub/akshare later via the router.
"""
from __future__ import annotations

import datetime as dt

import yfinance as yf

from ..markets import Market, infer_market
from .base import (
    Bar,
    CompanyProfile,
    Dividend,
    Financials,
    Fundamentals,
    HolderRow,
    MarketDataAdapter,
    NewsItem,
    Quote,
    Statement,
    StatementRow,
)

# Curated line items per statement: (display label, [possible yfinance index labels]).
_INCOME_ROWS = [
    ("营业收入", ["Total Revenue"]),
    ("营业成本", ["Cost Of Revenue"]),
    ("毛利", ["Gross Profit"]),
    ("研发费用", ["Research And Development"]),
    ("营业利润", ["Operating Income", "Total Operating Income As Reported"]),
    ("税前利润", ["Pretax Income"]),
    ("净利润", ["Net Income", "Net Income Common Stockholders"]),
    ("EBITDA", ["EBITDA", "Normalized EBITDA"]),
    ("摊薄EPS", ["Diluted EPS"]),
]
_BALANCE_ROWS = [
    ("总资产", ["Total Assets"]),
    ("总负债", ["Total Liabilities Net Minority Interest", "Total Liabilities"]),
    ("股东权益", ["Stockholders Equity", "Total Equity Gross Minority Interest"]),
    ("现金及等价物", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
    ("总债务", ["Total Debt"]),
    ("流动资产", ["Current Assets"]),
    ("流动负债", ["Current Liabilities"]),
]
_CASHFLOW_ROWS = [
    ("经营现金流", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
    ("资本开支", ["Capital Expenditure"]),
    ("自由现金流", ["Free Cash Flow"]),
    ("投资现金流", ["Investing Cash Flow"]),
    ("筹资现金流", ["Financing Cash Flow"]),
]


def _period_labels(df, quarterly: bool) -> list[str]:
    out: list[str] = []
    for col in df.columns:
        try:
            out.append(col.strftime("%Y-%m" if quarterly else "%Y"))
        except Exception:
            out.append(str(col))
    return out


def _find_row(df, names: list[str]):
    for n in names:
        if n in df.index:
            return df.loc[n]
    return None


def _statement(df, wanted, quarterly: bool) -> Statement:
    if df is None or getattr(df, "empty", True):
        return Statement()
    periods = _period_labels(df, quarterly)
    rows: list[StatementRow] = []
    for label, names in wanted:
        series = _find_row(df, names)
        if series is None:
            continue
        rows.append(StatementRow(label=label, values=[_f(v) for v in series.tolist()]))
    return Statement(periods=periods, rows=rows)


def _f(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _pct_str(s: str) -> float | None:
    """Parse an old-yfinance percent string like '12.34%' -> 0.1234."""
    try:
        return float(str(s).strip().rstrip("%")) / 100.0
    except (TypeError, ValueError):
        return None


class YFinanceAdapter(MarketDataAdapter):
    name = "yfinance"
    markets = (Market.US, Market.HK, Market.CN)

    def _ticker(self, symbol: str) -> yf.Ticker:
        return yf.Ticker(symbol)

    def get_quote(self, symbol: str) -> Quote:
        market = infer_market(symbol)
        t = self._ticker(symbol)
        price = prev = currency = name = None
        try:
            fi = t.fast_info
            price = _f(fi["lastPrice"])
            prev = _f(fi["previousClose"])
            currency = fi["currency"]
        except Exception:
            pass
        if price is None:
            # Fallback: derive from recent daily closes (reliable when fast_info is flaky).
            try:
                df = t.history(period="5d", interval="1d", auto_adjust=False)
                closes = [c for c in df["Close"].tolist() if c == c]
                if closes:
                    price = _f(closes[-1])
                    if prev is None and len(closes) >= 2:
                        prev = _f(closes[-2])
            except Exception:
                pass
        change = change_pct = None
        if price is not None and prev:
            change = price - prev
            change_pct = (change / prev) * 100 if prev else None
        return Quote(
            symbol=symbol, market=market, price=price, change=change,
            change_pct=change_pct, currency=currency, name=name,
            as_of=dt.datetime.now(dt.timezone.utc),
        )

    def get_ohlcv(self, symbol: str, period: str = "1y", interval: str = "1d") -> list[Bar]:
        t = self._ticker(symbol)
        try:
            df = t.history(period=period, interval=interval, auto_adjust=False)
        except Exception:
            return []
        bars: list[Bar] = []
        for idx, row in df.iterrows():
            d = idx.date() if hasattr(idx, "date") else idx
            o, h, low, c = _f(row.get("Open")), _f(row.get("High")), _f(row.get("Low")), _f(row.get("Close"))
            if None in (o, h, low, c):
                continue
            bars.append(Bar(date=d, open=o, high=h, low=low, close=c, volume=_f(row.get("Volume"))))
        return bars

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        market = infer_market(symbol)
        t = self._ticker(symbol)
        info: dict = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}
        g = info.get
        return Fundamentals(
            symbol=symbol, market=market,
            name=g("longName") or g("shortName"),
            sector=g("sector"), industry=g("industry"), currency=g("currency"),
            market_cap=_f(g("marketCap")), enterprise_value=_f(g("enterpriseValue")),
            pe_ttm=_f(g("trailingPE")), pe_fwd=_f(g("forwardPE")),
            pb=_f(g("priceToBook")), ps=_f(g("priceToSalesTrailing12Months")),
            peg=_f(g("trailingPegRatio") or g("pegRatio")), ev_ebitda=_f(g("enterpriseToEbitda")),
            gross_margin=_f(g("grossMargins")), operating_margin=_f(g("operatingMargins")),
            net_margin=_f(g("profitMargins")), roe=_f(g("returnOnEquity")), roa=_f(g("returnOnAssets")),
            revenue=_f(g("totalRevenue")), revenue_growth=_f(g("revenueGrowth")),
            eps=_f(g("trailingEps")), earnings_growth=_f(g("earningsGrowth")),
            dividend_yield=_f(g("dividendYield")), payout_ratio=_f(g("payoutRatio")),
            beta=_f(g("beta")), week52_high=_f(g("fiftyTwoWeekHigh")), week52_low=_f(g("fiftyTwoWeekLow")),
            shares_outstanding=_f(g("sharesOutstanding")), float_shares=_f(g("floatShares")),
            short_percent=_f(g("shortPercentOfFloat")), avg_volume=_f(g("averageVolume")),
            recommendation=g("recommendationKey"), recommendation_mean=_f(g("recommendationMean")),
            num_analysts=g("numberOfAnalystOpinions"),
            target_mean=_f(g("targetMeanPrice")), target_high=_f(g("targetHighPrice")),
            target_low=_f(g("targetLowPrice")), target_median=_f(g("targetMedianPrice")),
        )

    def get_recommendation_summary(self, symbol: str) -> dict[str, int] | None:
        """Latest analyst rating distribution (strongBuy/buy/hold/sell/strongSell counts).

        Powers the Futu-style 买入/持有/卖出 bars. yfinance's ``recommendations`` is a small
        DataFrame, newest period first; we take the most recent row. Returns None if absent."""
        t = self._ticker(symbol)
        try:
            df = t.recommendations
        except Exception:
            return None
        if df is None or getattr(df, "empty", True):
            return None
        try:
            row = df.iloc[0]
        except Exception:
            return None

        def _gi(key: str) -> int:
            try:
                v = row.get(key)
                return int(v) if v is not None and v == v else 0
            except (TypeError, ValueError):
                return 0

        out = {
            "strong_buy": _gi("strongBuy"), "buy": _gi("buy"), "hold": _gi("hold"),
            "sell": _gi("sell"), "strong_sell": _gi("strongSell"),
        }
        return out if sum(out.values()) > 0 else None

    def get_financials(self, symbol: str) -> Financials:
        market = infer_market(symbol)
        t = self._ticker(symbol)
        fin = Financials(symbol=symbol, market=market)

        def _df(attr):
            try:
                return getattr(t, attr)
            except Exception:
                return None

        inc, incq = _df("financials"), _df("quarterly_financials")
        bal, balq = _df("balance_sheet"), _df("quarterly_balance_sheet")
        cf, cfq = _df("cashflow"), _df("quarterly_cashflow")

        fin.income = _statement(inc, _INCOME_ROWS, quarterly=False)
        fin.income_q = _statement(incq, _INCOME_ROWS, quarterly=True)
        fin.balance = _statement(bal, _BALANCE_ROWS, quarterly=False)
        fin.balance_q = _statement(balq, _BALANCE_ROWS, quarterly=True)
        fin.cashflow = _statement(cf, _CASHFLOW_ROWS, quarterly=False)
        fin.cashflow_q = _statement(cfq, _CASHFLOW_ROWS, quarterly=True)

        # Derived annual FCF = Operating Cash Flow + Capital Expenditure (capex is negative).
        if cf is not None and not getattr(cf, "empty", True):
            fin.fcf_periods = _period_labels(cf, quarterly=False)
            direct = _find_row(cf, ["Free Cash Flow"])
            ocf = _find_row(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
            capex = _find_row(cf, ["Capital Expenditure"])
            for i in range(len(cf.columns)):
                val = None
                if direct is not None:
                    val = _f(direct.iloc[i])
                if val is None and ocf is not None:
                    o = _f(ocf.iloc[i])
                    c = _f(capex.iloc[i]) if capex is not None else 0.0
                    if o is not None:
                        val = o + (c or 0.0)
                fin.fcf.append(val)

        # Shares / cash / debt for the DCF bridge.
        info: dict = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}
        fin.currency = info.get("financialCurrency") or info.get("currency")
        fin.shares = _f(info.get("sharesOutstanding"))
        if bal is not None and not getattr(bal, "empty", True):
            cash_row = _find_row(bal, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
            debt_row = _find_row(bal, ["Total Debt"])
            if cash_row is not None:
                fin.cash = _f(cash_row.iloc[0])
            if debt_row is not None:
                fin.total_debt = _f(debt_row.iloc[0])
        if fin.total_debt is not None or fin.cash is not None:
            fin.net_debt = (fin.total_debt or 0.0) - (fin.cash or 0.0)
        return fin

    def get_profile(self, symbol: str) -> CompanyProfile:
        market = infer_market(symbol)
        t = self._ticker(symbol)
        prof = CompanyProfile(symbol=symbol, market=market)

        info: dict = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}
        g = info.get
        prof.name = g("longName") or g("shortName")
        prof.sector = g("sector")
        prof.industry = g("industry")
        prof.country = g("country")
        prof.website = g("website")
        prof.employees = g("fullTimeEmployees") if isinstance(g("fullTimeEmployees"), int) else None
        prof.summary = g("longBusinessSummary")
        prof.currency = g("currency")
        prof.dividend_yield = _f(g("dividendYield"))
        prof.payout_ratio = _f(g("payoutRatio"))

        # Dividend history (newest-first, last ~16 payments).
        try:
            divs = t.dividends
            if divs is not None and not divs.empty:
                rows: list[Dividend] = []
                for idx, amt in divs.items():
                    d = idx.date() if hasattr(idx, "date") else idx
                    a = _f(amt)
                    if a is not None and a > 0:
                        rows.append(Dividend(ex_date=d, amount=a))
                prof.dividends = list(reversed(rows))[:16]
        except Exception:
            pass

        # Ownership breakdown (% insiders / institutions).
        try:
            mh = t.major_holders
            if mh is not None and not mh.empty:
                # Newer yfinance: indexed DataFrame with a 'Value' column.
                if "Value" in getattr(mh, "columns", []):
                    prof.insiders_pct = _f(mh.loc["insidersPercentHeld", "Value"]) if "insidersPercentHeld" in mh.index else None
                    prof.institutions_pct = _f(mh.loc["institutionsPercentHeld", "Value"]) if "institutionsPercentHeld" in mh.index else None
                else:
                    # Older yfinance: 2-col [percent-string, label].
                    for _, r in mh.iterrows():
                        val, lbl = str(r.iloc[0]), str(r.iloc[1]).lower()
                        frac = _pct_str(val)
                        if "insider" in lbl:
                            prof.insiders_pct = frac
                        elif "institution" in lbl and "float" not in lbl:
                            prof.institutions_pct = frac
        except Exception:
            pass

        # Top institutional holders.
        try:
            ih = t.institutional_holders
            if ih is not None and not ih.empty:
                tops: list[HolderRow] = []
                for _, r in ih.head(10).iterrows():
                    name = r.get("Holder")
                    if not name:
                        continue
                    dr = r.get("Date Reported")
                    try:
                        dr = dr.date() if hasattr(dr, "date") else None
                    except Exception:
                        dr = None
                    tops.append(HolderRow(
                        name=str(name),
                        pct=_f(r.get("pctHeld")),
                        shares=_f(r.get("Shares")),
                        value=_f(r.get("Value")),
                        date_reported=dr,
                    ))
                prof.top_institutions = tops
        except Exception:
            pass

        return prof

    def get_news(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        t = self._ticker(symbol)
        try:
            raw = t.news or []
        except Exception:
            return []
        items: list[NewsItem] = []
        for n in raw[:limit]:
            # yfinance ≥0.2.4x nests under "content"; older versions are flat.
            c = n.get("content", n)
            title = c.get("title")
            if not title:
                continue
            pub = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher")
            url = None
            if isinstance(c.get("clickThroughUrl"), dict):
                url = c["clickThroughUrl"].get("url")
            url = url or c.get("canonicalUrl", {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else url
            url = url or c.get("link")
            published = None
            if c.get("pubDate"):
                try:
                    published = dt.datetime.fromisoformat(c["pubDate"].replace("Z", "+00:00"))
                except Exception:
                    published = None
            elif n.get("providerPublishTime"):
                published = dt.datetime.fromtimestamp(n["providerPublishTime"], dt.timezone.utc)
            items.append(NewsItem(title=title, publisher=pub, url=url, published_at=published))
        return items
