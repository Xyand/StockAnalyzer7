from datetime import date

import pytest

from backend.app.importers import (
    import_portfolio_csv,
    parse_date,
    parse_number,
    portfolio_to_csv,
    resolve_columns,
)


class TestParseNumber:
    @pytest.mark.parametrize("raw,expected", [
        ("1,234.56", 1234.56),
        ("$1,234.56", 1234.56),
        ("(500.00)", -500.0),
        ("-42", -42.0),
        ("12.5%", 12.5),
        ("", None),
        ("N/A", None),
        ("--", None),
        (None, None),
    ])
    def test_variants(self, raw, expected):
        assert parse_number(raw) == expected


class TestParseDate:
    @pytest.mark.parametrize("raw,expected", [
        ("2023-04-17", date(2023, 4, 17)),
        ("04/17/2023", date(2023, 4, 17)),
        ("17-Apr-2023", date(2023, 4, 17)),
        ("Apr 17, 2023", date(2023, 4, 17)),
        ("2023/04/17", date(2023, 4, 17)),
        ("not a date", None),
        ("", None),
    ])
    def test_variants(self, raw, expected):
        assert parse_date(raw) == expected


class TestResolveColumns:
    def test_cost_per_share_does_not_steal_the_total_cost_role(self):
        mapping = resolve_columns(["Symbol", "Quantity", "Cost Per Share", "Cost Basis"])
        assert mapping["unit_cost"] == "costpershare"
        assert mapping["total_cost"] == "costbasis"

    def test_a_column_is_claimed_by_one_role_only(self):
        mapping = resolve_columns(["Ticker", "Shares", "Cost Basis"])
        assert mapping["total_cost"] == "costbasis"
        assert mapping.get("unit_cost") != "costbasis"


class TestImportPortfolio:
    def test_canonical_layout(self):
        csv_text = (
            "symbol,quantity,cost_per_share,purchase_date,account\n"
            "AAPL,100,150.25,2021-03-04,Taxable\n"
            "MSFT,50,280.10,2022-07-19,IRA\n"
        )
        result = import_portfolio_csv(csv_text)
        assert result.rows_read == 2
        assert result.rows_skipped == 0
        lots = result.portfolio.lots
        assert [l.symbol for l in lots] == ["AAPL", "MSFT"]
        assert lots[0].cost_basis == pytest.approx(15025.0)
        assert lots[1].purchase_date == date(2022, 7, 19)

    def test_total_cost_is_converted_to_a_unit_cost(self):
        result = import_portfolio_csv("Symbol,Shares,Cost Basis\nVOO,20,8000\n")
        assert result.portfolio.lots[0].cost_per_share == pytest.approx(400.0)

    def test_broker_preamble_is_skipped(self):
        csv_text = (
            "Account Positions Export\n"
            "Generated 01/15/2025\n"
            "\n"
            "Symbol,Description,Quantity,Average Cost,Date Acquired\n"
            "NVDA,NVIDIA CORP,40,$412.55,01/09/2023\n"
        )
        result = import_portfolio_csv(csv_text)
        assert len(result.portfolio.lots) == 1
        lot = result.portfolio.lots[0]
        assert lot.symbol == "NVDA"
        assert lot.cost_per_share == pytest.approx(412.55)
        assert lot.purchase_date == date(2023, 1, 9)

    def test_multiple_lots_of_one_symbol_roll_up(self):
        csv_text = (
            "symbol,quantity,cost_per_share,purchase_date\n"
            "AAPL,100,50,2019-01-02\n"
            "AAPL,50,150,2022-01-03\n"
        )
        portfolio = import_portfolio_csv(csv_text).portfolio
        positions = portfolio.positions()
        assert len(positions) == 1
        assert positions[0].quantity == 150
        assert positions[0].cost_basis == pytest.approx(12500.0)
        assert positions[0].average_cost == pytest.approx(83.333, abs=1e-3)
        assert len(positions[0].lots) == 2

    def test_cash_row_becomes_a_cash_balance(self):
        csv_text = "symbol,quantity,cost_per_share\nCASH,2500,1.00\nAAPL,10,100\n"
        portfolio = import_portfolio_csv(csv_text).portfolio
        assert portfolio.cash == {"USD": 2500.0}
        assert len(portfolio.lots) == 1

    def test_row_without_quantity_is_skipped_with_a_warning(self):
        result = import_portfolio_csv("symbol,quantity\nAAPL,\nMSFT,10\n")
        assert result.rows_skipped == 1
        assert len(result.portfolio.lots) == 1
        assert any("no share quantity" in w for w in result.warnings)

    def test_missing_cost_warns_but_keeps_the_lot(self):
        result = import_portfolio_csv("symbol,quantity\nAAPL,10\n")
        assert len(result.portfolio.lots) == 1
        assert result.portfolio.lots[0].cost_per_share is None
        assert any("no cost recorded" in w for w in result.warnings)

    def test_file_without_a_symbol_column_is_rejected(self):
        result = import_portfolio_csv("date,amount\n2024-01-01,100\n")
        assert not result.portfolio.lots
        assert any("No symbol/ticker column" in w for w in result.warnings)

    def test_empty_file(self):
        result = import_portfolio_csv("")
        assert any("empty" in w.lower() for w in result.warnings)

    def test_symbols_are_uppercased_and_trimmed(self):
        portfolio = import_portfolio_csv("symbol,quantity\n  aapl ,10\n").portfolio
        assert portfolio.lots[0].symbol == "AAPL"

    def test_round_trip_through_csv(self):
        original = import_portfolio_csv(
            "symbol,quantity,cost_per_share,purchase_date\nAAPL,10,100,2023-01-05\n"
        ).portfolio
        restored = import_portfolio_csv(portfolio_to_csv(original)).portfolio
        assert restored.lots[0].symbol == original.lots[0].symbol
        assert restored.lots[0].quantity == original.lots[0].quantity
        assert restored.lots[0].purchase_date == original.lots[0].purchase_date
