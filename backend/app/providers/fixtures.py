"""Offline provider backed by the checked-in dataset in data/fixtures/.

Used for tests, for demos, and as the automatic fallback when the live
provider cannot be reached. The numbers are synthetic — see
scripts/build_fixtures.py.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from ..models import (
    AssetClass,
    FundComposition,
    FundHolding,
    PricePoint,
    Quote,
    SecurityInfo,
    SecurityType,
)
from .base import ProviderError, infer_asset_class


@lru_cache(maxsize=8)
def _load(directory: str, filename: str) -> dict:
    path = Path(directory) / filename
    if not path.exists():
        raise ProviderError(
            f"Fixture file {path} is missing. Run: python3 scripts/build_fixtures.py"
        )
    return json.loads(path.read_text())


class FixtureProvider:
    name = "fixtures"

    def __init__(self, fixtures_dir: Path) -> None:
        self.dir = str(fixtures_dir)

    @property
    def _securities(self) -> dict:
        return _load(self.dir, "securities.json")

    @property
    def _prices(self) -> dict:
        return _load(self.dir, "prices.json")

    @property
    def _funds(self) -> dict:
        return _load(self.dir, "fund_holdings.json")

    def known_symbols(self) -> list[str]:
        return sorted(self._securities)

    def get_info(self, symbol: str) -> SecurityInfo:
        raw = self._securities.get(symbol)
        if raw is None:
            raise ProviderError(f"{symbol} is not in the offline dataset")
        security_type = SecurityType(raw.get("security_type", "other"))
        name = raw.get("name")
        sector = raw.get("sector")
        return SecurityInfo(
            symbol=symbol,
            name=name,
            security_type=security_type,
            asset_class=infer_asset_class(name, security_type, sector),
            currency=raw.get("currency", "USD"),
            sector=sector,
            country=raw.get("country"),
            exchange=raw.get("exchange"),
        )

    def get_quote(self, symbol: str) -> Quote:
        series = self._prices.get(symbol)
        if not series:
            raise ProviderError(f"No offline prices for {symbol}")
        last = series[-1]
        return Quote(
            symbol=symbol,
            price=float(last["close"]),
            currency=self._securities.get(symbol, {}).get("currency", "USD"),
            as_of=date.fromisoformat(last["date"]),
        )

    def get_history(self, symbol: str, start: date, end: date) -> list[PricePoint]:
        series = self._prices.get(symbol)
        if not series:
            raise ProviderError(f"No offline prices for {symbol}")
        points = [
            PricePoint(
                date=date.fromisoformat(p["date"]),
                close=float(p["close"]),
                adj_close=float(p["adj_close"]),
            )
            for p in series
            if start <= date.fromisoformat(p["date"]) <= end
        ]
        if not points:
            raise ProviderError(f"No offline prices for {symbol} between {start} and {end}")
        return points

    def get_fund_composition(self, symbol: str) -> FundComposition | None:
        raw = self._funds.get(symbol)
        if raw is None:
            return None
        holdings = [
            FundHolding(
                symbol=h.get("symbol"),
                name=h.get("name"),
                weight=float(h["weight"]),
                asset_class=AssetClass(h["asset_class"]) if h.get("asset_class") else None,
                sector=h.get("sector"),
                country=h.get("country"),
            )
            for h in raw.get("holdings", [])
        ]
        return FundComposition(
            symbol=symbol,
            holdings=holdings,
            source=raw.get("source", "fixture"),
            partial=bool(raw.get("partial", False)),
            as_of=date.fromisoformat(raw["as_of"]) if raw.get("as_of") else None,
        )
