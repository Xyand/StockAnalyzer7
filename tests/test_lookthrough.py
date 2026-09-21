import pytest

from backend.app.models import AssetClass, FundComposition, FundHolding, SecurityInfo, SecurityType
from backend.app.services.exposure import build_report, concentration
from backend.app.services.lookthrough import LookthroughEngine


class FakeMarketData:
    """A tiny in-memory universe, so look-through behaviour is tested against
    compositions whose exact weights are known."""

    def __init__(self, infos, compositions, max_depth=4):
        self._infos = infos
        self._compositions = compositions

        class _S:
            max_lookthrough_depth = max_depth

        self.settings = _S()

    def get_info(self, symbol):
        if symbol not in self._infos:
            raise KeyError(symbol)
        return self._infos[symbol]

    def get_fund_composition(self, symbol):
        return self._compositions.get(symbol)


def stock(symbol, name, sector="Technology", country="United States"):
    return SecurityInfo(
        symbol=symbol, name=name, security_type=SecurityType.STOCK,
        asset_class=AssetClass.EQUITY, sector=sector, country=country,
    )


def fund(symbol, name):
    return SecurityInfo(
        symbol=symbol, name=name, security_type=SecurityType.ETF, asset_class=AssetClass.EQUITY
    )


def composition(symbol, rows, partial=False, source="test"):
    return FundComposition(
        symbol=symbol,
        source=source,
        partial=partial,
        holdings=[FundHolding(symbol=s, name=n, weight=w) for s, n, w in rows],
    )


@pytest.fixture
def universe():
    infos = {
        "AAA": stock("AAA", "Alpha Corp"),
        "BBB": stock("BBB", "Beta Corp", sector="Healthcare"),
        "CCC": stock("CCC", "Gamma Corp", country="Japan"),
        "FUND": fund("FUND", "Simple Fund"),
        "TOPFUND": fund("TOPFUND", "Top-Ten-Only Fund"),
        "FOF": fund("FOF", "Fund of Funds"),
        "LOOP": fund("LOOP", "Self-Referencing Fund"),
    }
    compositions = {
        "FUND": composition("FUND", [("AAA", None, 0.60), ("BBB", None, 0.40)]),
        "TOPFUND": composition("TOPFUND", [("AAA", None, 0.30)], partial=True),
        "FOF": composition("FOF", [("FUND", None, 0.50), ("CCC", None, 0.50)]),
        "LOOP": composition("LOOP", [("LOOP", None, 0.50), ("AAA", None, 0.50)]),
    }
    return FakeMarketData(infos, compositions)


class TestExpansion:
    def test_direct_stock_stays_a_single_leaf(self, universe):
        result = LookthroughEngine(universe).expand([("AAA", 1000.0)])
        assert len(result.leaves) == 1
        leaf = result.leaves[0]
        assert leaf.key == "AAA" and leaf.value == 1000.0 and leaf.depth == 0

    def test_fund_is_split_by_weight(self, universe):
        result = LookthroughEngine(universe).expand([("FUND", 1000.0)])
        by_key = {l.key: l.value for l in result.leaves}
        assert by_key == pytest.approx({"AAA": 600.0, "BBB": 400.0})
        assert all(l.depth == 1 for l in result.leaves)

    def test_direct_and_fund_held_exposure_combines(self, universe):
        result = LookthroughEngine(universe).expand([("AAA", 500.0), ("FUND", 1000.0)])
        report = build_report(result)
        alpha = next(r for r in report.by_asset if r.key == "AAA")
        assert alpha.value == pytest.approx(1100.0)
        assert alpha.direct_value == pytest.approx(500.0)
        assert alpha.indirect_value == pytest.approx(600.0)
        assert alpha.sources == pytest.approx({"AAA": 500.0, "FUND": 600.0})

    def test_fund_of_funds_recurses_through_both_layers(self, universe):
        result = LookthroughEngine(universe).expand([("FOF", 1000.0)])
        by_key = {l.key: l.value for l in result.leaves}
        # 50% into FUND, which is 60/40 AAA/BBB -> 300/200; 50% straight to CCC.
        assert by_key == pytest.approx({"AAA": 300.0, "BBB": 200.0, "CCC": 500.0})
        assert {l.key: l.depth for l in result.leaves}["AAA"] == 2

    def test_depth_limit_stops_recursion(self, universe):
        result = LookthroughEngine(universe, max_depth=1).expand([("FOF", 1000.0)])
        by_key = {l.key: l.value for l in result.leaves}
        assert by_key["FUND"] == pytest.approx(500.0)  # left unexpanded
        assert "AAA" not in by_key

    def test_circular_holding_is_reported_not_looped(self, universe):
        result = LookthroughEngine(universe).expand([("LOOP", 1000.0)])
        assert any("Circular holding" in w for w in result.warnings)
        assert sum(l.value for l in result.leaves) == pytest.approx(1000.0)

    def test_value_is_conserved(self, universe):
        result = LookthroughEngine(universe).expand([("AAA", 500.0), ("FOF", 1500.0)])
        assert result.total_value == pytest.approx(2000.0)


class TestUndisclosedWeight:
    def test_residual_becomes_an_unresolved_bucket(self, universe):
        result = LookthroughEngine(universe).expand([("TOPFUND", 1000.0)])
        assert result.resolved_value == pytest.approx(300.0)
        assert result.unresolved_value == pytest.approx(700.0)
        assert any("not disclosed" in w for w in result.warnings)

    def test_coverage_is_recorded(self, universe):
        result = LookthroughEngine(universe).expand([("TOPFUND", 1000.0)])
        assert result.coverage["TOPFUND"] == pytest.approx(0.30)

    def test_scale_to_full_prorates_the_tail(self, universe):
        result = LookthroughEngine(universe).expand([("TOPFUND", 1000.0)], scale_to_full=True)
        assert result.unresolved_value == pytest.approx(0.0)
        assert result.leaves[0].value == pytest.approx(1000.0)

    def test_report_weights_sum_to_one(self, universe):
        result = LookthroughEngine(universe).expand([("TOPFUND", 1000.0), ("AAA", 500.0)])
        report = build_report(result)
        assert sum(r.weight for r in report.by_asset) == pytest.approx(1.0)
        assert sum(r.weight for r in report.by_asset_class) == pytest.approx(1.0)


class TestGrouping:
    def test_sector_and_country_rollups(self, universe):
        result = LookthroughEngine(universe).expand([("FOF", 1000.0)])
        report = build_report(result)
        sectors = {r.label: r.value for r in report.by_sector}
        assert sectors["Technology"] == pytest.approx(800.0)   # AAA 300 + CCC 500
        assert sectors["Healthcare"] == pytest.approx(200.0)
        countries = {r.label: r.value for r in report.by_country}
        assert countries["Japan"] == pytest.approx(500.0)

    def test_concentration_excludes_undisclosed_buckets(self, universe):
        result = LookthroughEngine(universe).expand([("TOPFUND", 1000.0)])
        report = build_report(result)
        assert concentration(report.by_asset) == pytest.approx(0.30)


class TestAgainstFixtures:
    def test_sample_portfolio_conserves_value_and_finds_overlap(self, market_data, sample_portfolio):
        from datetime import date

        from backend.app.services.analyzer import PortfolioAnalyzer

        analysis = PortfolioAnalyzer(market_data).analyze(sample_portfolio, today=date(2025, 12, 26))
        holdings = [(h.symbol, h.market_value) for h in analysis.holdings if h.market_value]
        result = LookthroughEngine(market_data).expand(holdings)
        report = build_report(result)

        assert report.total_value == pytest.approx(sum(v for _, v in holdings), abs=1.0)
        nvda = next(r for r in report.by_asset if r.key == "NVDA")
        # Held directly and inside VOO, QQQ and VT: effective exposure exceeds
        # the direct position.
        assert nvda.value > nvda.direct_value
        assert len(nvda.sources) > 1
