"""Live market data via yfinance (Yahoo Finance). No API key required."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from ..models import (
    AssetClass,
    FundComposition,
    FundHolding,
    PricePoint,
    Quote,
    SecurityInfo,
    SecurityType,
)
from .base import ProviderError, infer_asset_class, map_quote_type
from .cache import DiskCache

log = logging.getLogger(__name__)


class YahooProvider:
    """Wraps yfinance behind the provider protocol.

    yfinance is imported lazily so the app still boots (in fixtures mode) on a
    machine where the package is missing.
    """

    name = "yahoo"

    def __init__(self, cache: DiskCache) -> None:
        self.cache = cache
        self._yf: Any | None = None

    @property
    def yf(self) -> Any:
        if self._yf is None:
            try:
                import yfinance  # noqa: PLC0415 - intentional lazy import
            except ImportError as exc:  # pragma: no cover - env specific
                raise ProviderError("yfinance is not installed; pip install -r requirements.txt") from exc
            self._yf = yfinance
        return self._yf

    def _ticker(self, symbol: str) -> Any:
        return self.yf.Ticker(symbol)

    # ---------------------------------------------------------------- info
    def get_info(self, symbol: str) -> SecurityInfo:
        cached = self.cache.get("info", symbol)
        if cached is not None:
            return SecurityInfo(**cached)
        try:
            raw = self._ticker(symbol).get_info() or {}
        except Exception as exc:  # yfinance raises a zoo of exception types
            raise ProviderError(f"Could not load info for {symbol}: {exc}") from exc

        security_type = map_quote_type(raw.get("quoteType"))
        name = raw.get("longName") or raw.get("shortName") or symbol
        sector = raw.get("sector")
        info = SecurityInfo(
            symbol=symbol,
            name=name,
            security_type=security_type,
            asset_class=infer_asset_class(name, security_type, sector),
            currency=(raw.get("currency") or "USD").upper(),
            sector=sector,
            industry=raw.get("industry"),
            country=raw.get("country"),
            exchange=raw.get("exchange"),
        )
        self.cache.set("info", symbol, info.model_dump(mode="json"))
        return info

    # --------------------------------------------------------------- quote
    def get_quote(self, symbol: str) -> Quote:
        cached = self.cache.get("quote", symbol)
        if cached is not None:
            return Quote(**cached)
        try:
            fast = self._ticker(symbol).fast_info
            price = fast.get("last_price") if hasattr(fast, "get") else fast.last_price
            currency = (fast.get("currency") if hasattr(fast, "get") else fast.currency) or "USD"
        except Exception as exc:
            raise ProviderError(f"Could not load a quote for {symbol}: {exc}") from exc
        if price is None:
            raise ProviderError(f"No price available for {symbol}")
        quote = Quote(symbol=symbol, price=float(price), currency=str(currency).upper(), as_of=date.today())
        self.cache.set("quote", symbol, quote.model_dump(mode="json"))
        return quote

    # ------------------------------------------------------------- history
    def get_history(self, symbol: str, start: date, end: date) -> list[PricePoint]:
        key = f"{symbol}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get("history", key)
        if cached is not None:
            return [PricePoint(**p) for p in cached]
        try:
            frame = self._ticker(symbol).history(
                start=start.isoformat(), end=end.isoformat(), auto_adjust=False, actions=True
            )
        except Exception as exc:
            raise ProviderError(f"Could not load history for {symbol}: {exc}") from exc
        if frame is None or frame.empty:
            raise ProviderError(f"No price history for {symbol} between {start} and {end}")

        points: list[PricePoint] = []
        has_adj = "Adj Close" in frame.columns
        for idx, row in frame.iterrows():
            close = row.get("Close")
            if close is None or close != close:  # NaN guard
                continue
            adj = row.get("Adj Close") if has_adj else None
            if adj is None or adj != adj:
                adj = close
            stamp = idx.date() if isinstance(idx, datetime) else idx
            points.append(PricePoint(date=stamp, close=float(close), adj_close=float(adj)))
        if not points:
            raise ProviderError(f"No usable price history for {symbol}")
        self.cache.set("history", key, [p.model_dump(mode="json") for p in points])
        return points

    # ------------------------------------------------------------ holdings
    def get_fund_composition(self, symbol: str) -> FundComposition | None:
        """Yahoo publishes only the fund's top ~10 positions.

        That is enough to be useful but never complete, so the result is always
        flagged ``partial`` and the look-through report surfaces the gap.
        """
        cached = self.cache.get("fund", symbol)
        if cached is not None:
            return FundComposition(**cached)
        try:
            funds_data = self._ticker(symbol).funds_data
            table = funds_data.top_holdings
        except Exception as exc:
            log.debug("No Yahoo fund data for %s: %s", symbol, exc)
            return None
        if table is None or getattr(table, "empty", True):
            return None

        holdings: list[FundHolding] = []
        for sym, row in table.iterrows():
            weight = row.get("Holding Percent")
            if weight is None or weight != weight:
                continue
            weight = float(weight)
            # Yahoo has shipped this column both as a fraction and as a percent.
            if weight > 1.0:
                weight /= 100.0
            name = row.get("Name")
            holdings.append(
                FundHolding(
                    symbol=str(sym) if sym else None,
                    name=str(name) if name else None,
                    weight=weight,
                )
            )
        if not holdings:
            return None
        composition = FundComposition(
            symbol=symbol,
            holdings=holdings,
            source="yahoo:top_holdings",
            partial=True,
            as_of=date.today(),
        )
        self.cache.set("fund", symbol, composition.model_dump(mode="json"))
        return composition

    # ---------------------------------------------------------------- misc
    def get_sector_weights(self, symbol: str) -> dict[str, float]:
        """Sector mix of a fund — used to model the part Yahoo does not list."""
        cached = self.cache.get("sectors", symbol)
        if cached is not None:
            return cached
        try:
            weights = self._ticker(symbol).funds_data.sector_weightings or {}
        except Exception:
            return {}
        cleaned = {str(k): float(v) for k, v in weights.items() if v is not None}
        total = sum(cleaned.values())
        if total > 1.5:  # percent, not fraction
            cleaned = {k: v / 100.0 for k, v in cleaned.items()}
        self.cache.set("sectors", symbol, cleaned)
        return cleaned


def asset_class_for(info: SecurityInfo) -> AssetClass:
    return info.asset_class
