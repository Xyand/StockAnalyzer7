"""Portfolio analysis: value every position, then measure how each has done."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from ..models import (
    AnalysisResponse,
    HoldingAnalysis,
    Portfolio,
    PortfolioSummary,
    Position,
    YearReturn,
)
from ..providers import MarketData, ProviderError
from .returns import (
    PriceSeries,
    dividend_flows,
    annualize,
    calendar_year_returns,
    position_cashflows,
    position_year_return,
    staleness_days,
    trailing_return,
    xirr,
)

log = logging.getLogger(__name__)

#: How much history to pull. Enough for the yearly table plus a margin so the
#: first year's opening price is available.
HISTORY_YEARS = 8


class PortfolioAnalyzer:
    def __init__(self, market_data: MarketData) -> None:
        self.md = market_data

    def analyze(self, portfolio: Portfolio, today: date | None = None) -> AnalysisResponse:
        today = today or date.today()
        start = date(today.year - HISTORY_YEARS, 1, 1)
        positions = portfolio.positions()

        warnings: list[str] = []
        holdings: list[HoldingAnalysis] = []
        series_by_symbol: dict[str, PriceSeries] = {}

        income_flows: list[tuple[date, float]] = []
        for position in positions:
            analysis, series = self._analyze_position(position, start, today)
            holdings.append(analysis)
            if series:
                series_by_symbol[position.symbol] = series
                income_flows.extend(dividend_flows(position.lots, series, None, today))

        total_value = sum(h.market_value or 0.0 for h in holdings)
        cash_total = sum(portfolio.cash.values())
        total_value += cash_total
        total_cost = sum(h.cost_basis for h in holdings) + cash_total

        for holding in holdings:
            if total_value and holding.market_value is not None:
                holding.weight = holding.market_value / total_value
            warnings.extend(holding.warnings)

        years = self._covered_years(holdings)
        summary = self._summarize(portfolio, holdings, total_value, total_cost, today, income_flows)

        notes = list(self.md.notes)
        return AnalysisResponse(
            summary=summary,
            holdings=holdings,
            years=years,
            warnings=notes + _dedupe(warnings),
            provider="fixtures" if self.md.degraded else self.md.active_provider,
        )

    # ------------------------------------------------------------------
    def _analyze_position(
        self, position: Position, start: date, today: date
    ) -> tuple[HoldingAnalysis, PriceSeries | None]:
        symbol = position.symbol
        analysis = HoldingAnalysis(
            symbol=symbol,
            quantity=position.quantity,
            cost_basis=position.cost_basis,
        )

        try:
            info = self.md.get_info(symbol)
            analysis.name = info.name
            analysis.security_type = info.security_type
            analysis.asset_class = info.asset_class
            analysis.currency = info.currency
        except ProviderError as exc:
            analysis.warnings.append(f"{symbol}: {exc}")

        try:
            points = self.md.get_history(symbol, start, today + timedelta(days=1))
        except ProviderError as exc:
            analysis.warnings.append(
                f"{symbol}: no price history available ({exc}). Value and returns are blank."
            )
            return analysis, None

        series = PriceSeries(points)
        last = series.points[-1]
        try:
            quote = self.md.get_quote(symbol)
            price = quote.price
        except ProviderError:
            price = last.close
        analysis.price = price
        analysis.market_value = price * position.quantity

        if position.cost_basis:
            analysis.unrealized_pl = analysis.market_value - position.cost_basis
            analysis.unrealized_pl_pct = analysis.unrealized_pl / position.cost_basis
        else:
            analysis.warnings.append(
                f"{symbol}: no cost basis recorded, so profit and loss cannot be computed."
            )

        analysis.ttm_market_return = trailing_return(series, today)
        stale = staleness_days(series, today)
        if stale > 7:
            analysis.warnings.append(
                f"{symbol}: the newest price available is from {series.last_date} "
                f"({stale} days ago). Returns are measured to that date."
            )

        # Money-weighted return over the whole holding period.
        flows, flow_warnings = position_cashflows(
            position.lots, series, today, analysis.market_value or 0.0
        )
        analysis.warnings.extend(flow_warnings)
        if flows:
            first_purchase = min(d for d, _ in flows)
            analysis.holding_period_days = (today - first_purchase).days
            invested = -sum(a for _, a in flows if a < 0)
            returned = sum(a for _, a in flows if a > 0)
            if invested > 0:
                analysis.total_return_since_purchase = returned / invested - 1.0
            rate = xirr(flows)
            if rate is not None:
                analysis.annualized_return = rate
            elif analysis.total_return_since_purchase is not None and analysis.holding_period_days:
                analysis.annualized_return = annualize(
                    analysis.total_return_since_purchase, analysis.holding_period_days
                )

        analysis.yearly = self._yearly(position, series, today)
        return analysis, series

    # ------------------------------------------------------------------
    def _yearly(self, position: Position, series: PriceSeries, today: date) -> list[YearReturn]:
        first_purchase = min(
            (lot.purchase_date for lot in position.lots if lot.purchase_date), default=None
        )
        first_year = first_purchase.year if first_purchase else today.year - 5
        first_year = max(first_year, series.points[0].date.year)
        years = list(range(first_year, today.year + 1))

        market = calendar_year_returns(series, years)
        rows: list[YearReturn] = []
        for year in years:
            row = market.get(year) or YearReturn(year=year)
            rate, partial = position_year_return(position.lots, series, year, today)
            row.position_return = rate
            row.partial = row.partial or partial
            if row.market_return is None and row.position_return is None:
                continue
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    def _covered_years(self, holdings: list[HoldingAnalysis]) -> list[int]:
        years: set[int] = set()
        for holding in holdings:
            years.update(row.year for row in holding.yearly)
        return sorted(years)

    def _summarize(
        self,
        portfolio: Portfolio,
        holdings: list[HoldingAnalysis],
        total_value: float,
        total_cost: float,
        today: date,
        income_flows: list[tuple[date, float]] | None = None,
    ) -> PortfolioSummary:
        unrealized = total_value - total_cost

        # Portfolio TTM return: value-weighted across holdings that have one.
        weighted, weight_sum = 0.0, 0.0
        for holding in holdings:
            if holding.ttm_market_return is not None and holding.market_value:
                weighted += holding.ttm_market_return * holding.market_value
                weight_sum += holding.market_value
        ttm = weighted / weight_sum if weight_sum else None

        # Portfolio XIRR over every dated lot.
        all_flows: list[tuple[date, float]] = [
            (lot.purchase_date, -lot.cost_per_share * lot.quantity)
            for lot in portfolio.lots
            if lot.purchase_date and lot.cost_per_share is not None
        ]
        if all_flows:
            # Dividends across every holding, on the dates they were paid.
            all_flows.extend(income_flows or [])
            if total_value:
                all_flows.append((today, total_value))
        portfolio_rate = xirr(all_flows) if all_flows else None

        return PortfolioSummary(
            total_value=round(total_value, 2),
            total_cost=round(total_cost, 2),
            unrealized_pl=round(unrealized, 2),
            unrealized_pl_pct=(unrealized / total_cost) if total_cost else None,
            base_currency=portfolio.base_currency,
            holdings_count=len(holdings),
            ttm_return=ttm,
            annualized_return=portfolio_rate,
            as_of=today,
        )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
