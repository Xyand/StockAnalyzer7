#!/usr/bin/env python3
"""Generate the offline fixture dataset in data/fixtures/.

The fixtures let the whole app — analysis, look-through, exposure, the UI — run
and be tested with no network access. Prices are a seeded random walk pinned to
plausible per-year drifts, so figures are realistic in shape but are NOT real
market history and must never be read as such.

Re-run with:  python3 scripts/build_fixtures.py
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "fixtures"
START = date(2018, 1, 5)
END = date(2025, 12, 26)

# symbol -> (name, type, sector, country, start price, dividend yield,
#            {year: total return}, annual volatility)
UNIVERSE: dict[str, dict] = {
    "AAPL": dict(name="Apple Inc.", type="stock", sector="Technology", country="United States",
                 price=43.0, div=0.006, vol=0.28,
                 returns={2018: -0.05, 2019: 0.89, 2020: 0.82, 2021: 0.34, 2022: -0.26, 2023: 0.49, 2024: 0.31, 2025: 0.12}),
    "MSFT": dict(name="Microsoft Corporation", type="stock", sector="Technology", country="United States",
                 price=88.0, div=0.008, vol=0.26,
                 returns={2018: 0.21, 2019: 0.58, 2020: 0.43, 2021: 0.52, 2022: -0.28, 2023: 0.58, 2024: 0.13, 2025: 0.18}),
    "NVDA": dict(name="NVIDIA Corporation", type="stock", sector="Technology", country="United States",
                 price=12.0, div=0.001, vol=0.52,
                 returns={2018: -0.31, 2019: 0.77, 2020: 1.22, 2021: 1.25, 2022: -0.50, 2023: 2.39, 2024: 1.71, 2025: 0.35}),
    "AMZN": dict(name="Amazon.com, Inc.", type="stock", sector="Consumer Cyclical", country="United States",
                 price=59.0, div=0.0, vol=0.33,
                 returns={2018: 0.28, 2019: 0.23, 2020: 0.76, 2021: 0.02, 2022: -0.50, 2023: 0.81, 2024: 0.44, 2025: 0.09}),
    "GOOGL": dict(name="Alphabet Inc.", type="stock", sector="Communication Services", country="United States",
                  price=53.0, div=0.004, vol=0.29,
                  returns={2018: -0.01, 2019: 0.28, 2020: 0.31, 2021: 0.65, 2022: -0.39, 2023: 0.58, 2024: 0.36, 2025: 0.22}),
    "META": dict(name="Meta Platforms, Inc.", type="stock", sector="Communication Services", country="United States",
                 price=181.0, div=0.004, vol=0.40,
                 returns={2018: -0.26, 2019: 0.57, 2020: 0.33, 2021: 0.23, 2022: -0.64, 2023: 1.94, 2024: 0.65, 2025: 0.14}),
    "TSLA": dict(name="Tesla, Inc.", type="stock", sector="Consumer Cyclical", country="United States",
                 price=21.0, div=0.0, vol=0.60,
                 returns={2018: 0.07, 2019: 0.26, 2020: 7.43, 2021: 0.50, 2022: -0.65, 2023: 1.02, 2024: 0.63, 2025: -0.08}),
    "JNJ": dict(name="Johnson & Johnson", type="stock", sector="Healthcare", country="United States",
                price=140.0, div=0.028, vol=0.16,
                returns={2018: -0.05, 2019: 0.16, 2020: 0.11, 2021: 0.11, 2022: 0.06, 2023: -0.09, 2024: 0.02, 2025: 0.07}),
    "JPM": dict(name="JPMorgan Chase & Co.", type="stock", sector="Financial Services", country="United States",
                price=107.0, div=0.025, vol=0.24,
                returns={2018: -0.07, 2019: 0.47, 2020: -0.06, 2021: 0.28, 2022: -0.12, 2023: 0.31, 2024: 0.44, 2025: 0.15}),
    "XOM": dict(name="Exxon Mobil Corporation", type="stock", sector="Energy", country="United States",
                price=84.0, div=0.041, vol=0.28,
                returns={2018: -0.15, 2019: 0.07, 2020: -0.36, 2021: 0.57, 2022: 0.87, 2023: -0.05, 2024: 0.09, 2025: 0.04}),
    "BRK-B": dict(name="Berkshire Hathaway Inc.", type="stock", sector="Financial Services", country="United States",
                  price=198.0, div=0.0, vol=0.17,
                  returns={2018: 0.03, 2019: 0.11, 2020: 0.02, 2021: 0.29, 2022: 0.04, 2023: 0.16, 2024: 0.27, 2025: 0.11}),
    "UNH": dict(name="UnitedHealth Group Incorporated", type="stock", sector="Healthcare", country="United States",
                price=220.0, div=0.014, vol=0.22,
                returns={2018: 0.14, 2019: 0.18, 2020: 0.21, 2021: 0.44, 2022: 0.07, 2023: 0.01, 2024: 0.02, 2025: -0.12}),
    "V": dict(name="Visa Inc.", type="stock", sector="Financial Services", country="United States",
              price=114.0, div=0.007, vol=0.21,
              returns={2018: 0.16, 2019: 0.43, 2020: 0.17, 2021: 0.00, 2022: -0.03, 2023: 0.26, 2024: 0.22, 2025: 0.10}),
    "PG": dict(name="The Procter & Gamble Company", type="stock", sector="Consumer Defensive", country="United States",
               price=92.0, div=0.024, vol=0.15,
               returns={2018: 0.03, 2019: 0.39, 2020: 0.14, 2021: 0.21, 2022: -0.03, 2023: 0.02, 2024: 0.14, 2025: 0.05}),
    "HD": dict(name="The Home Depot, Inc.", type="stock", sector="Consumer Cyclical", country="United States",
               price=180.0, div=0.023, vol=0.22,
               returns={2018: -0.08, 2019: 0.31, 2020: 0.25, 2021: 0.59, 2022: -0.22, 2023: 0.13, 2024: 0.14, 2025: 0.06}),
    "ASML": dict(name="ASML Holding N.V.", type="stock", sector="Technology", country="Netherlands",
                 price=175.0, div=0.009, vol=0.33,
                 returns={2018: -0.05, 2019: 0.83, 2020: 0.60, 2021: 0.66, 2022: -0.30, 2023: 0.37, 2024: -0.04, 2025: 0.25}),
    "TSM": dict(name="Taiwan Semiconductor Manufacturing Company Limited", type="stock", sector="Technology", country="Taiwan",
                price=38.0, div=0.017, vol=0.32,
                returns={2018: -0.02, 2019: 0.59, 2020: 0.90, 2021: 0.11, 2022: -0.36, 2023: 0.41, 2024: 0.90, 2025: 0.20}),
    # --- Funds -------------------------------------------------------------
    "VOO": dict(name="Vanguard S&P 500 ETF", type="etf", sector=None, country="United States",
                price=247.0, div=0.015, vol=0.17,
                returns={2018: -0.04, 2019: 0.31, 2020: 0.18, 2021: 0.29, 2022: -0.18, 2023: 0.26, 2024: 0.25, 2025: 0.13}),
    "QQQ": dict(name="Invesco QQQ Trust", type="etf", sector=None, country="United States",
                price=156.0, div=0.006, vol=0.23,
                returns={2018: -0.01, 2019: 0.39, 2020: 0.49, 2021: 0.27, 2022: -0.33, 2023: 0.55, 2024: 0.25, 2025: 0.16}),
    "VTI": dict(name="Vanguard Total Stock Market ETF", type="etf", sector=None, country="United States",
                price=138.0, div=0.015, vol=0.18,
                returns={2018: -0.05, 2019: 0.31, 2020: 0.21, 2021: 0.26, 2022: -0.20, 2023: 0.26, 2024: 0.24, 2025: 0.12}),
    "VXUS": dict(name="Vanguard Total International Stock ETF", type="etf", sector=None, country="Global",
                 price=56.0, div=0.030, vol=0.17,
                 returns={2018: -0.14, 2019: 0.22, 2020: 0.11, 2021: 0.09, 2022: -0.16, 2023: 0.15, 2024: 0.05, 2025: 0.14}),
    "BND": dict(name="Vanguard Total Bond Market ETF", type="etf", sector=None, country="United States",
                price=80.0, div=0.030, vol=0.05,
                returns={2018: -0.00, 2019: 0.09, 2020: 0.08, 2021: -0.02, 2022: -0.13, 2023: 0.06, 2024: 0.01, 2025: 0.04}),
    "AGG": dict(name="iShares Core U.S. Aggregate Bond ETF", type="etf", sector=None, country="United States",
                price=107.0, div=0.030, vol=0.05,
                returns={2018: -0.00, 2019: 0.09, 2020: 0.08, 2021: -0.02, 2022: -0.13, 2023: 0.06, 2024: 0.01, 2025: 0.04}),
    "SCHD": dict(name="Schwab U.S. Dividend Equity ETF", type="etf", sector=None, country="United States",
                 price=50.0, div=0.035, vol=0.15,
                 returns={2018: -0.06, 2019: 0.27, 2020: 0.15, 2021: 0.30, 2022: -0.03, 2023: 0.05, 2024: 0.11, 2025: 0.07}),
    "VNQ": dict(name="Vanguard Real Estate ETF", type="etf", sector="Real Estate", country="United States",
                price=83.0, div=0.038, vol=0.20,
                returns={2018: -0.06, 2019: 0.29, 2020: -0.05, 2021: 0.40, 2022: -0.26, 2023: 0.12, 2024: 0.05, 2025: 0.03}),
    "GLD": dict(name="SPDR Gold Shares", type="etf", sector=None, country="Global",
                price=124.0, div=0.0, vol=0.14,
                returns={2018: -0.02, 2019: 0.18, 2020: 0.25, 2021: -0.04, 2022: -0.01, 2023: 0.13, 2024: 0.26, 2025: 0.28}),
    "IEMG": dict(name="iShares Core MSCI Emerging Markets ETF", type="etf", sector=None, country="Global",
                 price=59.0, div=0.025, vol=0.19,
                 returns={2018: -0.15, 2019: 0.19, 2020: 0.18, 2021: -0.04, 2022: -0.20, 2023: 0.11, 2024: 0.09, 2025: 0.16}),
    "VT": dict(name="Vanguard Total World Stock ETF", type="etf", sector=None, country="Global",
               price=74.0, div=0.021, vol=0.17,
               returns={2018: -0.10, 2019: 0.27, 2020: 0.17, 2021: 0.18, 2022: -0.18, 2023: 0.22, 2024: 0.17, 2025: 0.13}),
    "AOR": dict(name="iShares Core Growth Allocation ETF", type="etf", sector=None, country="Global",
                price=44.0, div=0.022, vol=0.11,
                returns={2018: -0.06, 2019: 0.20, 2020: 0.13, 2021: 0.11, 2022: -0.17, 2023: 0.15, 2024: 0.11, 2025: 0.09}),
}

# Fund compositions. Weights are fractions of NAV and intentionally do not sum
# to 1 for broad-market funds — the untracked tail is the report's "unresolved"
# bucket, exactly as it is with real data.
COMPOSITIONS: dict[str, dict] = {
    "VOO": dict(source="fixture:issuer", partial=True, holdings=[
        ("NVDA", None, 0.0741), ("AAPL", None, 0.0654), ("MSFT", None, 0.0629),
        ("AMZN", None, 0.0398), ("META", None, 0.0287), ("AVGO", "Broadcom Inc.", 0.0246),
        ("GOOGL", None, 0.0232), ("TSLA", None, 0.0201), ("BRK-B", None, 0.0164),
        ("JPM", None, 0.0146), ("UNH", None, 0.0121), ("V", None, 0.0104),
        ("XOM", None, 0.0102), ("JNJ", None, 0.0088), ("PG", None, 0.0085),
        ("HD", None, 0.0079),
    ]),
    "QQQ": dict(source="fixture:issuer", partial=True, holdings=[
        ("NVDA", None, 0.0912), ("AAPL", None, 0.0881), ("MSFT", None, 0.0803),
        ("AMZN", None, 0.0561), ("META", None, 0.0421), ("AVGO", "Broadcom Inc.", 0.0389),
        ("GOOGL", None, 0.0312), ("TSLA", None, 0.0298), ("COST", "Costco Wholesale Corporation", 0.0251),
        ("NFLX", "Netflix, Inc.", 0.0198), ("ASML", None, 0.0081),
    ]),
    "VTI": dict(source="fixture:issuer", partial=True, holdings=[
        ("NVDA", None, 0.0662), ("AAPL", None, 0.0584), ("MSFT", None, 0.0561),
        ("AMZN", None, 0.0355), ("META", None, 0.0256), ("AVGO", "Broadcom Inc.", 0.0219),
        ("GOOGL", None, 0.0207), ("TSLA", None, 0.0179), ("BRK-B", None, 0.0146),
        ("JPM", None, 0.0130), ("UNH", None, 0.0108), ("V", None, 0.0093),
    ]),
    "VXUS": dict(source="fixture:issuer", partial=True, holdings=[
        ("TSM", None, 0.0281), ("ASML", None, 0.0112),
        ("NVO", "Novo Nordisk A/S", 0.0081), ("NESN.SW", "Nestle S.A.", 0.0078),
        ("SAP", "SAP SE", 0.0074), ("7203.T", "Toyota Motor Corporation", 0.0068),
        ("BABA", "Alibaba Group Holding Limited", 0.0064), ("HSBC", "HSBC Holdings plc", 0.0059),
    ]),
    "IEMG": dict(source="fixture:issuer", partial=True, holdings=[
        ("TSM", None, 0.0932), ("BABA", "Alibaba Group Holding Limited", 0.0281),
        ("0700.HK", "Tencent Holdings Limited", 0.0412),
        ("005930.KS", "Samsung Electronics Co., Ltd.", 0.0301),
        ("INFY", "Infosys Limited", 0.0091),
    ]),
    "SCHD": dict(source="fixture:issuer", partial=True, holdings=[
        ("XOM", None, 0.0431), ("JNJ", None, 0.0402), ("PG", None, 0.0398),
        ("HD", None, 0.0389), ("KO", "The Coca-Cola Company", 0.0381),
        ("PEP", "PepsiCo, Inc.", 0.0374), ("CVX", "Chevron Corporation", 0.0369),
        ("ABBV", "AbbVie Inc.", 0.0361),
    ]),
    "VNQ": dict(source="fixture:issuer", partial=True, holdings=[
        ("PLD", "Prologis, Inc.", 0.0721), ("AMT", "American Tower Corporation", 0.0612),
        ("EQIX", "Equinix, Inc.", 0.0521), ("SPG", "Simon Property Group, Inc.", 0.0402),
        ("O", "Realty Income Corporation", 0.0361), ("PSA", "Public Storage", 0.0331),
    ]),
    "BND": dict(source="fixture:issuer", partial=False, holdings=[
        (None, "U.S. Treasury Notes & Bonds", 0.4610),
        (None, "U.S. Government Mortgage-Backed Securities", 0.2080),
        (None, "Investment-Grade Corporate Credit", 0.2390),
        (None, "Government Agency & Supranational Debt", 0.0560),
        (None, "Cash & Cash Equivalents", 0.0360),
    ]),
    "AGG": dict(source="fixture:issuer", partial=False, holdings=[
        (None, "U.S. Treasury Notes & Bonds", 0.4450),
        (None, "U.S. Government Mortgage-Backed Securities", 0.2610),
        (None, "Investment-Grade Corporate Credit", 0.2440),
        (None, "Government Agency & Supranational Debt", 0.0310),
        (None, "Cash & Cash Equivalents", 0.0190),
    ]),
    "GLD": dict(source="fixture:issuer", partial=False, holdings=[
        (None, "Gold Bullion", 0.9982),
        (None, "Cash & Cash Equivalents", 0.0018),
    ]),
    # Funds of funds — these exercise recursive look-through.
    "VT": dict(source="fixture:issuer", partial=False, holdings=[
        ("VTI", None, 0.6230), ("VXUS", None, 0.3740),
        (None, "Cash & Cash Equivalents", 0.0030),
    ]),
    "AOR": dict(source="fixture:issuer", partial=False, holdings=[
        ("VTI", None, 0.4180), ("VXUS", None, 0.2410),
        ("AGG", None, 0.2760), (None, "International Bond Sleeve", 0.0610),
        (None, "Cash & Cash Equivalents", 0.0040),
    ]),
}

ASSET_CLASS_BY_NAME = {
    "U.S. Treasury Notes & Bonds": "bond",
    "U.S. Government Mortgage-Backed Securities": "bond",
    "Investment-Grade Corporate Credit": "bond",
    "Government Agency & Supranational Debt": "bond",
    "International Bond Sleeve": "bond",
    "Cash & Cash Equivalents": "cash",
    "Gold Bullion": "commodity",
}


def trading_days(start: date, end: date) -> list[date]:
    """Weekly Friday-ish sampling — dense enough for every metric we compute,
    small enough to keep the fixture files readable in a diff."""
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=7)
    return days


def build_series(symbol: str, spec: dict) -> list[dict]:
    rng = random.Random(f"stockanalyzer7:{symbol}")
    days = trading_days(START, END)
    by_year: dict[int, list[date]] = {}
    for day in days:
        by_year.setdefault(day.year, []).append(day)

    price = spec["price"]
    div_yield = spec["div"]
    vol = spec["vol"]
    points: list[dict] = []
    # adj_close carries reinvested dividends; close is the raw price.
    adj_factor = 1.0

    for year in sorted(by_year):
        year_days = by_year[year]
        n = len(year_days)
        total_return = spec["returns"].get(year, 0.05)
        price_return = (1 + total_return) / (1 + div_yield) - 1
        # Per-step drift that compounds to the year's price return exactly.
        drift = math.log1p(price_return) / n
        step_vol = vol / math.sqrt(52)
        shocks = [rng.gauss(0.0, step_vol) for _ in range(n)]
        mean_shock = sum(shocks) / n
        shocks = [s - mean_shock for s in shocks]  # keep the year's total on target
        div_step = div_yield / n
        for day, shock in zip(year_days, shocks):
            price *= math.exp(drift + shock)
            adj_factor *= 1 + div_step
            points.append(
                {
                    "date": day.isoformat(),
                    "close": round(price, 4),
                    "adj_close": round(price * adj_factor, 4),
                }
            )
    return points


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    info: dict[str, dict] = {}
    prices: dict[str, list[dict]] = {}
    for symbol, spec in UNIVERSE.items():
        prices[symbol] = build_series(symbol, spec)
        info[symbol] = {
            "symbol": symbol,
            "name": spec["name"],
            "security_type": spec["type"],
            "sector": spec["sector"],
            "country": spec["country"],
            "currency": "USD",
            "exchange": "NMS",
        }

    compositions: dict[str, dict] = {}
    for symbol, spec in COMPOSITIONS.items():
        holdings = []
        for sym, name, weight in spec["holdings"]:
            label = name or (UNIVERSE.get(sym, {}).get("name") if sym else None)
            entry = {"symbol": sym, "name": label, "weight": weight}
            if label in ASSET_CLASS_BY_NAME:
                entry["asset_class"] = ASSET_CLASS_BY_NAME[label]
            holdings.append(entry)
        compositions[symbol] = {
            "symbol": symbol,
            "source": spec["source"],
            "partial": spec["partial"],
            "as_of": END.isoformat(),
            "holdings": holdings,
        }

    (OUT / "securities.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    (OUT / "prices.json").write_text(json.dumps(prices, separators=(",", ":"), sort_keys=True) + "\n")
    (OUT / "fund_holdings.json").write_text(json.dumps(compositions, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(info)} securities, {len(compositions)} fund compositions to {OUT}")


if __name__ == "__main__":
    main()
