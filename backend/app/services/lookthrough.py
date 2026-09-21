"""Fund look-through: turn a portfolio of tickers into base-asset exposure.

If you hold VOO, QQQ and AAPL, you do not hold three things — you hold Apple
several times over. This module unwinds every fund into its constituents,
recursively (a fund of funds such as VT or AOR is expanded through both
layers), and reports what fraction of the portfolio it could and could not
explain.

The unexplained part is never hidden. A free data source that publishes only a
fund's top ten positions leaves most of a broad-market fund unaccounted for,
and a report that quietly renormalizes that away would overstate every
position it *does* know about.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import AssetClass, SecurityInfo, SecurityType
from ..providers import MarketData
from ..providers.base import infer_asset_class

log = logging.getLogger(__name__)

#: Cap on metadata lookups for constituents we have never seen, so a portfolio
#: of broad-market funds does not fire off hundreds of requests.
MAX_ENRICH_LOOKUPS = 60

UNRESOLVED_KEY = "__unresolved__"


@dataclass
class Leaf:
    """One base-asset exposure produced by unwinding a position."""

    key: str
    label: str
    value: float
    #: The portfolio ticker this exposure came from.
    origin: str
    #: 0 = held directly, 1 = via one fund, 2 = via a fund of funds, ...
    depth: int
    asset_class: AssetClass | None = None
    sector: str | None = None
    country: str | None = None
    resolved: bool = True
    #: The fund whose composition we could not fully explain.
    unresolved_from: str | None = None


@dataclass
class LookthroughResult:
    leaves: list[Leaf] = field(default_factory=list)
    #: symbol -> fraction of that fund's NAV we could account for.
    coverage: dict[str, float] = field(default_factory=dict)
    #: symbol -> where its composition came from.
    sources: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return sum(leaf.value for leaf in self.leaves)

    @property
    def resolved_value(self) -> float:
        return sum(leaf.value for leaf in self.leaves if leaf.resolved)

    @property
    def unresolved_value(self) -> float:
        return sum(leaf.value for leaf in self.leaves if not leaf.resolved)


class LookthroughEngine:
    def __init__(self, market_data: MarketData, max_depth: int | None = None) -> None:
        self.md = market_data
        self.max_depth = max_depth if max_depth is not None else market_data.settings.max_lookthrough_depth
        self._info_cache: dict[str, SecurityInfo | None] = {}
        self._lookups = 0

    # ------------------------------------------------------------------
    def _info(self, symbol: str, budgeted: bool = True) -> SecurityInfo | None:
        if symbol in self._info_cache:
            return self._info_cache[symbol]
        if budgeted and self._lookups >= MAX_ENRICH_LOOKUPS:
            return None
        self._lookups += 1
        try:
            info = self.md.get_info(symbol)
        except Exception as exc:
            log.debug("No info for %s: %s", symbol, exc)
            info = None
        self._info_cache[symbol] = info
        return info

    def _is_fund(self, symbol: str, info: SecurityInfo | None) -> bool:
        if info is not None and info.security_type.is_fund:
            return True
        # Even without metadata, a published composition proves it is a fund.
        return info is None and self.md.get_fund_composition(symbol) is not None

    # ------------------------------------------------------------------
    def expand(
        self,
        holdings: list[tuple[str, float]],
        scale_to_full: bool = False,
    ) -> LookthroughResult:
        """Unwind every position into base assets.

        Args:
            holdings: (symbol, market value) pairs.
            scale_to_full: pro-rate a fund's untracked tail across the
                constituents we do know, instead of reporting it separately.
                Useful when a source publishes only the top ten and you want a
                best-estimate shape rather than a coverage-honest one.
        """
        result = LookthroughResult()
        for symbol, value in holdings:
            if value is None or value == 0:
                continue
            self._expand_one(symbol, value, symbol, 0, (symbol,), result, scale_to_full)
        return result

    def _expand_one(
        self,
        symbol: str,
        value: float,
        origin: str,
        depth: int,
        path: tuple[str, ...],
        result: LookthroughResult,
        scale_to_full: bool,
    ) -> None:
        info = self._info(symbol, budgeted=depth > 0)

        composition = None
        if depth < self.max_depth and self._is_fund(symbol, info):
            composition = self.md.get_fund_composition(symbol)
            if composition is None and info is not None and info.security_type.is_fund:
                result.warnings.append(
                    f"No holdings data for {symbol} ({info.name or 'fund'}); it is shown as a "
                    "single line instead of being broken down. Drop its holdings CSV in "
                    "data/etf_holdings/ for a full breakdown."
                )

        if composition is None or not composition.holdings:
            result.leaves.append(self._leaf(symbol, value, origin, depth, info))
            return

        covered = composition.covered_weight
        result.coverage[symbol] = covered
        result.sources[symbol] = composition.source

        scale = 1.0
        if scale_to_full and covered > 0:
            scale = 1.0 / covered

        for holding in composition.holdings:
            child_value = value * holding.weight * scale
            if not child_value:
                continue
            child_symbol = holding.symbol
            if child_symbol and child_symbol in path:
                # A fund that (directly or otherwise) holds itself: stop here
                # rather than looping, and keep the value visible.
                result.warnings.append(
                    f"Circular holding detected: {' -> '.join(path)} -> {child_symbol}."
                )
                result.leaves.append(
                    self._leaf_from_holding(holding, child_value, origin, depth + 1)
                )
                continue

            if child_symbol and depth + 1 < self.max_depth:
                child_info = self._info(child_symbol)
                if child_info is not None and child_info.security_type.is_fund:
                    self._expand_one(
                        child_symbol,
                        child_value,
                        origin,
                        depth + 1,
                        path + (child_symbol,),
                        result,
                        scale_to_full,
                    )
                    continue
                if child_info is not None:
                    result.leaves.append(
                        self._leaf(child_symbol, child_value, origin, depth + 1, child_info)
                    )
                    continue
            result.leaves.append(self._leaf_from_holding(holding, child_value, origin, depth + 1))

        # Whatever the composition does not account for.
        if not scale_to_full:
            residual_weight = 1.0 - covered
            if residual_weight > 0.0005:
                label = f"Not disclosed ({symbol})"
                result.leaves.append(
                    Leaf(
                        key=f"{UNRESOLVED_KEY}:{symbol}",
                        label=label,
                        value=value * residual_weight,
                        origin=origin,
                        depth=depth + 1,
                        asset_class=None,
                        resolved=False,
                        unresolved_from=symbol,
                    )
                )
                if composition.partial:
                    result.warnings.append(
                        f"{symbol}: only the top {len(composition.holdings)} positions "
                        f"({covered:.1%} of the fund) are published by {composition.source}. "
                        f"The remaining {residual_weight:.1%} is shown as \"not disclosed\"."
                    )

    # ------------------------------------------------------------------
    def _leaf(
        self, symbol: str, value: float, origin: str, depth: int, info: SecurityInfo | None
    ) -> Leaf:
        if info is None:
            return Leaf(
                key=symbol,
                label=symbol,
                value=value,
                origin=origin,
                depth=depth,
                asset_class=None,
                resolved=True,
            )
        return Leaf(
            key=symbol,
            label=info.name or symbol,
            value=value,
            origin=origin,
            depth=depth,
            asset_class=info.asset_class,
            sector=info.sector,
            country=info.country,
            resolved=True,
        )

    def _leaf_from_holding(self, holding, value: float, origin: str, depth: int) -> Leaf:
        """A constituent we have no security record for — bonds, foreign lines,
        cash sleeves. Its own metadata is all we get, which is usually enough."""
        key = holding.symbol or (holding.name or "Unknown").strip().upper()
        asset_class = holding.asset_class
        if asset_class is None:
            inferred = infer_asset_class(holding.name, SecurityType.OTHER, holding.sector)
            asset_class = inferred if inferred is not AssetClass.OTHER else None
        return Leaf(
            key=key,
            label=holding.name or holding.symbol or "Unknown",
            value=value,
            origin=origin,
            depth=depth,
            asset_class=asset_class,
            sector=holding.sector,
            country=holding.country,
            resolved=True,
        )
