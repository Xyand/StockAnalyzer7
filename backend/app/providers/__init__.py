"""Provider wiring.

`MarketData` is the single entry point the services use. It picks the
configured live provider, falls back to the offline fixtures when the live one
cannot be reached, and resolves fund compositions from the best source
available for each symbol.
"""
from __future__ import annotations

import logging
from datetime import date

from ..config import Settings, get_settings
from ..models import FundComposition, PricePoint, Quote, SecurityInfo
from .base import ProviderError
from .cache import DiskCache
from .fixtures import FixtureProvider
from .holdings_files import HoldingsFileProvider, parse_holdings_csv
from .yahoo import YahooProvider

log = logging.getLogger(__name__)

__all__ = [
    "MarketData",
    "ProviderError",
    "DiskCache",
    "FixtureProvider",
    "YahooProvider",
    "HoldingsFileProvider",
    "parse_holdings_csv",
    "get_market_data",
]


class MarketData:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cache = DiskCache(self.settings.cache_dir, self.settings.cache_ttl_seconds)
        self.fixtures = FixtureProvider(self.settings.fixtures_dir)
        self.files = HoldingsFileProvider(
            self.settings.etf_holdings_dir, self.settings.allow_issuer_downloads
        )

        if self.settings.market_data_provider == "fixtures":
            self.live = None
            self.active_provider = "fixtures"
        else:
            self.live = YahooProvider(self.cache)
            self.active_provider = self.live.name
        #: Set once a live call fails and we switch to fixtures, so the UI can say so.
        self.degraded = False
        self.notes: list[str] = []

    # ------------------------------------------------------------------
    def _note(self, message: str) -> None:
        if message not in self.notes:
            self.notes.append(message)

    def _with_fallback(self, symbol: str, call: str, *args):
        """Run `call` on the live provider, falling back to fixtures on failure."""
        if self.live is not None:
            try:
                return getattr(self.live, call)(*args)
            except ProviderError as exc:
                log.info("Live provider failed for %s (%s): %s", symbol, call, exc)
                if not self.settings.fallback_to_fixtures:
                    raise
                self.degraded = True
                self._note(
                    "Live market data was unreachable; showing the offline demo dataset instead."
                )
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Unexpected live provider error for %s: %s", symbol, exc)
                if not self.settings.fallback_to_fixtures:
                    raise ProviderError(str(exc)) from exc
                self.degraded = True
                self._note("Live market data was unreachable; showing the offline demo dataset instead.")
        return getattr(self.fixtures, call)(*args)

    # ------------------------------------------------------------------
    def get_info(self, symbol: str) -> SecurityInfo:
        return self._with_fallback(symbol, "get_info", symbol)

    def get_quote(self, symbol: str) -> Quote:
        return self._with_fallback(symbol, "get_quote", symbol)

    def get_history(self, symbol: str, start: date, end: date) -> list[PricePoint]:
        return self._with_fallback(symbol, "get_history", symbol, start, end)

    # ------------------------------------------------------------------
    def get_fund_composition(self, symbol: str) -> FundComposition | None:
        """Best available composition for a fund.

        Preference order, because coverage is what makes look-through honest:
          1. a complete issuer holdings file (local CSV or registered URL)
          2. the offline fixture dataset
          3. the live quote API's top-N list (partial by construction)
        """
        from_file = self.files.get_fund_composition(symbol)
        if from_file is not None and not from_file.partial:
            return from_file

        candidates: list[FundComposition] = [c for c in (from_file,) if c is not None]

        try:
            fixture = self.fixtures.get_fund_composition(symbol)
        except ProviderError:
            fixture = None
        if fixture is not None:
            if not fixture.partial:
                return fixture
            candidates.append(fixture)

        if self.live is not None:
            try:
                live = self.live.get_fund_composition(symbol)
            except Exception as exc:  # pragma: no cover - network dependent
                log.debug("Live fund composition failed for %s: %s", symbol, exc)
                live = None
            if live is not None:
                candidates.append(live)

        if not candidates:
            return None
        # All partial — keep whichever explains the most of the fund.
        return max(candidates, key=lambda c: c.covered_weight)

    def known_symbols(self) -> list[str]:
        return self.fixtures.known_symbols()


_market_data: MarketData | None = None


def get_market_data(fresh: bool = False) -> MarketData:
    global _market_data
    if fresh or _market_data is None:
        _market_data = MarketData()
    return _market_data
