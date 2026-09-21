"""Return mathematics.

Two different questions get answered per holding, and conflating them is the
classic portfolio-tool mistake:

* **Market return** — what the security did over a period (price + dividends),
  independent of when you bought. Comparable across holdings and to an index.
* **Position return** — what *your money* did, which depends on the size and
  timing of every purchase. Computed money-weighted (XIRR), so a lot bought
  last month cannot flatter a position held for five years.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from datetime import date, timedelta

from ..models import Lot, PricePoint, YearReturn

DAYS_PER_YEAR = 365.0


# --------------------------------------------------------------------------
# XIRR
# --------------------------------------------------------------------------

def _npv(rate: float, flows: list[tuple[date, float]], t0: date) -> float:
    total = 0.0
    for when, amount in flows:
        years = (when - t0).days / DAYS_PER_YEAR
        total += amount / ((1.0 + rate) ** years)
    return total


def xirr(flows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """Annualized money-weighted return of an irregular cash-flow series.

    Sign convention: money leaving your pocket is negative, money coming back
    (including the closing market value) is positive.

    Returns None when the series cannot define a rate — fewer than two flows,
    all flows the same sign, or no root in a sane range.
    """
    flows = [(d, float(a)) for d, a in flows if a]
    if len(flows) < 2:
        return None
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return None

    flows.sort(key=lambda f: f[0])
    t0 = flows[0][0]
    if all(d == t0 for d, _ in flows):
        return None

    # Newton-Raphson first: fast and almost always sufficient.
    rate = guess
    for _ in range(64):
        value = _npv(rate, flows, t0)
        if abs(value) < 1e-9:
            return rate
        step = 1e-6 * max(1.0, abs(rate))
        derivative = (_npv(rate + step, flows, t0) - value) / step
        if derivative == 0 or not math.isfinite(derivative):
            break
        next_rate = rate - value / derivative
        if not math.isfinite(next_rate) or next_rate <= -0.9999995:
            break
        if abs(next_rate - rate) < 1e-10:
            return next_rate
        rate = next_rate

    # Bisection fallback over a wide bracket — slower but robust. The lower
    # bound sits just above -100% so that a near-total loss still brackets a
    # root instead of being reported as "no answer".
    low, high = -0.999999, 10.0
    f_low, f_high = _npv(low, flows, t0), _npv(high, flows, t0)
    if f_low * f_high > 0:
        return None
    for _ in range(300):
        mid = (low + high) / 2.0
        f_mid = _npv(mid, flows, t0)
        if abs(f_mid) < 1e-9:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


# --------------------------------------------------------------------------
# Price series helpers
# --------------------------------------------------------------------------

class PriceSeries:
    """Sorted price history with as-of lookups."""

    def __init__(self, points: list[PricePoint]) -> None:
        self.points = sorted(points, key=lambda p: p.date)
        self._dates = [p.date for p in self.points]

    def __bool__(self) -> bool:
        return bool(self.points)

    @property
    def first_date(self) -> date | None:
        return self._dates[0] if self._dates else None

    @property
    def last_date(self) -> date | None:
        return self._dates[-1] if self._dates else None

    def as_of(self, when: date) -> PricePoint | None:
        """Most recent point on or before `when`."""
        if not self.points:
            return None
        index = bisect_right(self._dates, when)
        return self.points[index - 1] if index else None

    def nearest(self, when: date, tolerance_days: int = 10) -> PricePoint | None:
        """Closest point in either direction — used for purchase dates that fall
        before the series starts or on a market holiday."""
        if not self.points:
            return None
        before = self.as_of(when)
        index = bisect_right(self._dates, when)
        after = self.points[index] if index < len(self.points) else None
        candidates = [p for p in (before, after) if p is not None]
        if not candidates:
            return None
        best = min(candidates, key=lambda p: abs((p.date - when).days))
        if abs((best.date - when).days) > tolerance_days and before is not None:
            return before
        return best

    def total_return(self, start: date, end: date) -> float | None:
        """Dividend-reinvested return between two dates."""
        a, b = self.as_of(start), self.as_of(end)
        if a is None or b is None or a.adj_close <= 0 or a.date >= b.date:
            return None
        return b.adj_close / a.adj_close - 1.0


def calendar_year_returns(series: PriceSeries, years: list[int]) -> dict[int, YearReturn]:
    """Total return for each calendar year the series covers.

    The first year is only reported when the series starts early enough to
    measure it; a partial year (the current one) is flagged rather than
    annualized, because annualizing three months of data is noise.
    """
    results: dict[int, YearReturn] = {}
    if not series:
        return results

    for year in years:
        prior_year_end = date(year - 1, 12, 31)
        year_end = date(year, 12, 31)
        start_point = series.as_of(prior_year_end)
        if start_point is None:
            # No data before this year — measure from the first point we have,
            # but only if that is early in the year, else skip.
            first = series.points[0]
            if first.date.year != year or first.date > date(year, 2, 15):
                continue
            start_point = first
        end_point = series.as_of(year_end)
        if end_point is None or end_point.date <= start_point.date:
            continue
        partial = end_point.date < date(year, 12, 20)
        results[year] = YearReturn(
            year=year,
            market_return=end_point.adj_close / start_point.adj_close - 1.0,
            start_value=start_point.close,
            end_value=end_point.close,
            partial=partial,
        )
    return results


# --------------------------------------------------------------------------
# Position-level returns
# --------------------------------------------------------------------------

def position_cashflows(
    lots: list[Lot],
    series: PriceSeries,
    valuation_date: date,
    market_value: float,
) -> tuple[list[tuple[date, float]], list[str]]:
    """Cash-flow series for one position: a negative flow per purchase, plus
    today's market value as the closing positive flow."""
    flows: list[tuple[date, float]] = []
    warnings: list[str] = []

    for lot in lots:
        if lot.purchase_date is None:
            warnings.append(
                f"{lot.symbol}: a lot has no purchase date, so it is left out of the "
                "annualized (money-weighted) return."
            )
            continue
        cost = lot.cost_per_share
        if cost is None:
            point = series.nearest(lot.purchase_date)
            if point is None:
                warnings.append(
                    f"{lot.symbol}: no cost and no price on {lot.purchase_date}; lot skipped."
                )
                continue
            cost = point.close
            warnings.append(
                f"{lot.symbol}: no cost recorded for the {lot.purchase_date} lot; used the "
                f"closing price of {cost:,.2f}."
            )
        flows.append((lot.purchase_date, -cost * lot.quantity))

    if flows and market_value:
        flows.append((valuation_date, market_value))
    return flows, warnings


def position_year_return(
    lots: list[Lot],
    series: PriceSeries,
    year: int,
    today: date,
) -> tuple[float | None, bool]:
    """Money-weighted return of the actual position over one calendar year.

    Opens the year with the position's market value as a negative flow, adds
    each purchase made during the year, and closes with the year-end value.
    """
    year_start = date(year, 1, 1)
    year_end = min(date(year, 12, 31), today)
    if year_start > today:
        return None, True

    dated_lots = [lot for lot in lots if lot.purchase_date is not None]
    if not dated_lots:
        return None, False

    opening_qty = sum(lot.quantity for lot in dated_lots if lot.purchase_date < year_start)
    during = [lot for lot in dated_lots if year_start <= lot.purchase_date <= year_end]
    if opening_qty <= 0 and not during:
        return None, False

    flows: list[tuple[date, float]] = []
    open_point = series.as_of(date(year - 1, 12, 31)) or series.nearest(year_start)
    if opening_qty > 0:
        if open_point is None:
            return None, False
        flows.append((year_start, -opening_qty * open_point.close))

    for lot in during:
        price = lot.cost_per_share
        if price is None:
            point = series.nearest(lot.purchase_date)
            if point is None:
                continue
            price = point.close
        flows.append((lot.purchase_date, -price * lot.quantity))

    close_point = series.as_of(year_end)
    if close_point is None or close_point.date.year != year:
        # The series ends before this year began, so there is nothing to
        # measure — do not carry a stale close forward into a phantom year.
        return None, False
    closing_qty = opening_qty + sum(lot.quantity for lot in during)
    flows.append((close_point.date, closing_qty * close_point.close))

    # Dividends received during the year, approximated from the gap between
    # price return and total return on the adjusted series.
    if open_point is not None and open_point.close > 0 and open_point.adj_close > 0:
        price_ret = close_point.close / open_point.close - 1.0
        total_ret = close_point.adj_close / open_point.adj_close - 1.0
        income_ret = total_ret - price_ret
        if income_ret > 0:
            flows.append((close_point.date, opening_qty * open_point.close * income_ret))

    rate = xirr(flows)
    held_full_year = opening_qty > 0 and year_end >= date(year, 12, 20)
    return rate, not held_full_year


def annualize(total_return: float, days: int) -> float | None:
    """Convert a cumulative return over `days` into an annual rate."""
    if days <= 0:
        return None
    years = days / DAYS_PER_YEAR
    base = 1.0 + total_return
    if base <= 0:
        return -1.0
    if years < 1 / 12:  # under a month: annualizing is meaningless
        return None
    return base ** (1.0 / years) - 1.0


def trailing_return(series: PriceSeries, today: date, days: int = 365) -> float | None:
    """Total return over the last `days`, anchored to the most recent price.

    Anchoring to the wall clock instead would silently shorten the window
    whenever the feed lags — over a weekend, a holiday, or a stale cache — and
    report a three-month figure under a twelve-month heading.
    """
    anchor = series.last_date
    if anchor is None:
        return None
    anchor = min(anchor, today)
    return series.total_return(anchor - timedelta(days=days), anchor)


def staleness_days(series: PriceSeries, today: date) -> int:
    last = series.last_date
    return (today - last).days if last else 0
