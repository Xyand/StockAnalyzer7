from datetime import date

import pytest

from backend.app.models import Lot, PricePoint
from backend.app.services.returns import (
    PriceSeries,
    annualize,
    calendar_year_returns,
    position_year_return,
    trailing_return,
    xirr,
)


def _series(pairs, dividend_factor=1.0):
    points = []
    factor = 1.0
    for d, close in pairs:
        points.append(PricePoint(date=d, close=close, adj_close=close * factor))
        factor *= dividend_factor
    return PriceSeries(points)


class TestXirr:
    def test_simple_doubling_over_one_year(self):
        rate = xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 2000)])
        assert rate == pytest.approx(1.0, abs=1e-4)

    def test_flat_investment_returns_zero(self):
        rate = xirr([(date(2020, 1, 1), -5000), (date(2025, 1, 1), 5000)])
        assert rate == pytest.approx(0.0, abs=1e-6)

    def test_loss_is_negative(self):
        rate = xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 750)])
        assert rate == pytest.approx(-0.25, abs=1e-3)

    def test_multiple_contributions(self):
        # Two equal contributions a year apart, ending at 2400 one year after
        # the second: a 10% annual rate compounds 1000 -> 1210 and 1000 -> 1100.
        rate = xirr([
            (date(2022, 1, 1), -1000),
            (date(2023, 1, 1), -1000),
            (date(2024, 1, 1), 2310),
        ])
        assert rate == pytest.approx(0.10, abs=1e-3)

    def test_total_loss_floors_at_minus_one(self):
        rate = xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 0.01)])
        assert rate is not None and rate < -0.99

    @pytest.mark.parametrize("flows", [
        [],
        [(date(2024, 1, 1), -100)],
        [(date(2024, 1, 1), -100), (date(2025, 1, 1), -50)],   # all negative
        [(date(2024, 1, 1), 100), (date(2025, 1, 1), 50)],     # all positive
        [(date(2024, 1, 1), -100), (date(2024, 1, 1), 150)],   # same day
    ])
    def test_undefined_series_return_none(self, flows):
        assert xirr(flows) is None


class TestAnnualize:
    def test_two_year_doubling(self):
        assert annualize(1.0, 730) == pytest.approx(2 ** 0.5 - 1, abs=1e-4)

    def test_sub_month_period_is_not_annualized(self):
        assert annualize(0.05, 10) is None

    def test_total_wipeout(self):
        assert annualize(-1.0, 365) == -1.0

    def test_zero_days(self):
        assert annualize(0.2, 0) is None


class TestPriceSeries:
    def test_as_of_picks_latest_point_at_or_before(self):
        series = _series([(date(2024, 1, 5), 10.0), (date(2024, 1, 12), 11.0)])
        assert series.as_of(date(2024, 1, 8)).close == 10.0
        assert series.as_of(date(2024, 1, 12)).close == 11.0
        assert series.as_of(date(2024, 1, 1)) is None

    def test_nearest_can_look_forward(self):
        series = _series([(date(2024, 3, 1), 50.0)])
        assert series.nearest(date(2024, 2, 28)).close == 50.0

    def test_total_return_uses_adjusted_close(self):
        series = _series([(date(2024, 1, 1), 100.0), (date(2025, 1, 1), 100.0)], dividend_factor=1.05)
        # Price is flat but dividends were paid, so total return is positive.
        assert series.total_return(date(2024, 1, 1), date(2025, 1, 1)) == pytest.approx(0.05, abs=1e-6)

    def test_trailing_return(self):
        series = _series([(date(2024, 1, 1), 100.0), (date(2025, 1, 1), 120.0)])
        assert trailing_return(series, date(2025, 1, 1)) == pytest.approx(0.20, abs=1e-6)


class TestCalendarYearReturns:
    def test_full_year_return(self):
        series = _series([
            (date(2022, 12, 30), 100.0),
            (date(2023, 6, 30), 110.0),
            (date(2023, 12, 29), 125.0),
        ])
        result = calendar_year_returns(series, [2023])
        assert result[2023].market_return == pytest.approx(0.25, abs=1e-6)
        assert result[2023].partial is False

    def test_year_without_prior_data_is_skipped(self):
        series = _series([(date(2023, 7, 1), 100.0), (date(2023, 12, 29), 120.0)])
        assert 2023 not in calendar_year_returns(series, [2023])

    def test_incomplete_current_year_is_flagged(self):
        series = _series([(date(2023, 12, 29), 100.0), (date(2024, 5, 1), 108.0)])
        assert calendar_year_returns(series, [2024])[2024].partial is True


class TestPositionYearReturn:
    def test_held_all_year_matches_market(self):
        series = _series([
            (date(2022, 12, 30), 100.0),
            (date(2023, 12, 29), 120.0),
        ])
        lots = [Lot(symbol="X", quantity=10, cost_per_share=80.0, purchase_date=date(2021, 5, 1))]
        rate, partial = position_year_return(lots, series, 2023, date(2024, 6, 1))
        assert rate == pytest.approx(0.20, abs=0.02)
        assert partial is False

    def test_bought_mid_year_is_flagged_partial(self):
        series = _series([
            (date(2022, 12, 30), 100.0),
            (date(2023, 7, 3), 110.0),
            (date(2023, 12, 29), 121.0),
        ])
        lots = [Lot(symbol="X", quantity=10, cost_per_share=110.0, purchase_date=date(2023, 7, 3))]
        rate, partial = position_year_return(lots, series, 2023, date(2024, 6, 1))
        assert partial is True
        assert rate is not None and rate > 0

    def test_year_before_first_purchase_has_no_return(self):
        series = _series([(date(2021, 12, 30), 90.0), (date(2022, 12, 30), 100.0)])
        lots = [Lot(symbol="X", quantity=5, cost_per_share=100.0, purchase_date=date(2023, 1, 5))]
        rate, _ = position_year_return(lots, series, 2022, date(2024, 1, 1))
        assert rate is None

    def test_undated_lots_yield_nothing(self):
        series = _series([(date(2022, 12, 30), 100.0), (date(2023, 12, 29), 120.0)])
        lots = [Lot(symbol="X", quantity=5, cost_per_share=100.0)]
        assert position_year_return(lots, series, 2023, date(2024, 1, 1)) == (None, False)


class TestStaleData:
    def test_trailing_return_anchors_to_the_last_price_not_today(self):
        # Prices stop nine months before "today": the window must still span a
        # year of data, not shrink to whatever is left.
        series = _series([
            (date(2023, 12, 29), 100.0),
            (date(2024, 9, 6), 130.0),
            (date(2025, 1, 3), 150.0),
        ])
        assert trailing_return(series, date(2025, 9, 20)) == pytest.approx(0.50, abs=1e-6)

    def test_a_window_the_history_cannot_cover_returns_none(self):
        # Six months of history cannot produce a twelve-month return, and
        # silently reporting the six-month figure would mislabel it.
        series = _series([(date(2025, 6, 2), 100.0), (date(2025, 9, 1), 110.0)])
        assert trailing_return(series, date(2025, 9, 20)) is None

    def test_a_year_after_the_data_ends_has_no_position_return(self):
        series = _series([(date(2024, 12, 27), 100.0)])
        lots = [Lot(symbol="X", quantity=10, cost_per_share=50.0, purchase_date=date(2023, 1, 5))]
        assert position_year_return(lots, series, 2025, date(2025, 9, 20)) == (None, False)
