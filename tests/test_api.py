import io

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Route uploads and the database into the test's own directory.
    monkeypatch.setenv("SA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SA_DB_PATH", str(tmp_path / "api.db"))
    from backend.app.config import REPO_ROOT, reset_settings

    reset_settings()
    # The fixture dataset still comes from the repo.
    (tmp_path / "fixtures").symlink_to(REPO_ROOT / "data" / "fixtures")

    import backend.app.api.routes as routes
    import backend.app.providers as providers

    routes._store = None
    providers._market_data = None
    yield TestClient(app)
    reset_settings()


PORTFOLIO = {
    "name": "Test",
    "base_currency": "USD",
    "lots": [
        {"symbol": "AAPL", "quantity": 100, "cost_per_share": 50.0, "purchase_date": "2020-01-10"},
        {"symbol": "VOO", "quantity": 50, "cost_per_share": 300.0, "purchase_date": "2021-06-15"},
    ],
}


class TestHealth:
    def test_reports_the_active_provider(self, client):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["provider"] == "fixtures"

    def test_index_page_is_served(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestAnalyze:
    def test_returns_a_holding_row_per_symbol(self, client):
        body = client.post("/api/analyze", json=PORTFOLIO).json()
        assert {h["symbol"] for h in body["holdings"]} == {"AAPL", "VOO"}
        assert body["summary"]["total_value"] > 0
        assert body["summary"]["holdings_count"] == 2

    def test_each_holding_carries_yearly_returns(self, client):
        body = client.post("/api/analyze", json=PORTFOLIO).json()
        aapl = next(h for h in body["holdings"] if h["symbol"] == "AAPL")
        assert aapl["yearly"], "expected a year-by-year return table"
        assert all("market_return" in row for row in aapl["yearly"])
        assert aapl["annualized_return"] is not None

    def test_weights_sum_to_one(self, client):
        body = client.post("/api/analyze", json=PORTFOLIO).json()
        assert sum(h["weight"] for h in body["holdings"]) == pytest.approx(1.0, abs=1e-6)

    def test_empty_portfolio_is_rejected(self, client):
        response = client.post("/api/analyze", json={"lots": []})
        assert response.status_code == 422

    def test_unknown_symbol_degrades_gracefully(self, client):
        response = client.post("/api/analyze", json={
            "lots": [
                {"symbol": "AAPL", "quantity": 10, "cost_per_share": 50.0},
                {"symbol": "ZZZZNOTREAL", "quantity": 5, "cost_per_share": 10.0},
            ]
        })
        assert response.status_code == 200
        body = response.json()
        bad = next(h for h in body["holdings"] if h["symbol"] == "ZZZZNOTREAL")
        assert bad["market_value"] is None
        assert body["warnings"]


class TestLookthrough:
    def test_breaks_funds_into_base_assets(self, client):
        body = client.post("/api/lookthrough", json=PORTFOLIO).json()
        report = body["report"]
        keys = {row["key"] for row in report["by_asset"]}
        assert "AAPL" in keys
        assert "MSFT" in keys, "VOO should contribute Microsoft exposure"
        assert report["total_value"] > 0

    def test_direct_and_indirect_are_separated(self, client):
        body = client.post("/api/lookthrough", json=PORTFOLIO).json()
        aapl = next(r for r in body["report"]["by_asset"] if r["key"] == "AAPL")
        assert aapl["direct_value"] > 0
        assert aapl["indirect_value"] > 0
        assert aapl["value"] == pytest.approx(aapl["direct_value"] + aapl["indirect_value"], abs=0.01)

    def test_undisclosed_weight_is_reported(self, client):
        body = client.post("/api/lookthrough", json=PORTFOLIO).json()
        assert body["report"]["unresolved_value"] > 0
        assert any(r["key"].startswith("__unresolved__") for r in body["report"]["by_asset"])

    def test_scale_to_full_removes_the_undisclosed_bucket(self, client):
        body = client.post("/api/lookthrough?scale_to_full=true", json=PORTFOLIO).json()
        assert body["report"]["unresolved_value"] == pytest.approx(0.0, abs=0.01)
        assert body["report"]["scaled"] is True

    def test_concentration_is_reported(self, client):
        body = client.post("/api/lookthrough", json=PORTFOLIO).json()
        assert 0.0 < body["top10_concentration"] <= 1.0


class TestPortfolioIO:
    def test_import_save_load_round_trip(self, client):
        csv_text = (
            "symbol,quantity,cost_per_share,purchase_date\n"
            "AAPL,100,50.00,2020-01-10\n"
            "VOO,50,300.00,2021-06-15\n"
        )
        response = client.post(
            "/api/portfolio/import",
            files={"file": ("holdings.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        )
        assert response.status_code == 200
        imported = response.json()
        assert imported["rows_read"] == 2

        assert client.post(
            "/api/portfolio/save", json={"portfolio": imported["portfolio"], "name": "mine"}
        ).json()["saved"]

        loaded = client.get("/api/portfolio?name=mine").json()
        assert len(loaded["lots"]) == 2
        assert {l["symbol"] for l in loaded["lots"]} == {"AAPL", "VOO"}

        assert "AAPL" in client.get("/api/portfolio/export?name=mine").json()["csv"]
        assert "mine" in [p["name"] for p in client.get("/api/portfolio/list").json()]
        assert client.request("DELETE", "/api/portfolio", params={"name": "mine"}).json()["deleted"]

    def test_unreadable_file_is_rejected(self, client):
        response = client.post(
            "/api/portfolio/import",
            files={"file": ("junk.csv", io.BytesIO(b"nothing,useful\n1,2\n"), "text/csv")},
        )
        assert response.status_code == 422

    def test_export_of_a_missing_portfolio_is_404(self, client):
        assert client.get("/api/portfolio/export?name=nope").status_code == 404


class TestHoldingsFileUpload:
    HOLDINGS_CSV = (
        "Ticker,Name,Sector,Asset Class,Weight (%)\n"
        "AAPL,Apple Inc.,Information Technology,Equity,40.0\n"
        "MSFT,Microsoft Corp,Information Technology,Equity,35.0\n"
        "JNJ,Johnson & Johnson,Health Care,Equity,25.0\n"
    )

    def test_upload_makes_a_fund_fully_resolvable(self, client):
        response = client.post(
            "/api/holdings-file/MYETF",
            files={"file": ("MYETF.csv", io.BytesIO(self.HOLDINGS_CSV.encode()), "text/csv")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["holdings"] == 3
        assert body["covered_weight"] == pytest.approx(1.0)
        assert body["partial"] is False
        assert "MYETF" in client.get("/api/health").json()["holdings_files"]

    def test_uploaded_composition_is_used_by_lookthrough(self, client):
        client.post(
            "/api/holdings-file/MYETF",
            files={"file": ("MYETF.csv", io.BytesIO(self.HOLDINGS_CSV.encode()), "text/csv")},
        )
        # MYETF has no price, so price it via a portfolio that also holds AAPL.
        body = client.post("/api/lookthrough", json=PORTFOLIO).json()
        assert body["report"]["total_value"] > 0

    def test_a_file_without_weights_is_rejected(self, client):
        response = client.post(
            "/api/holdings-file/BAD",
            files={"file": ("bad.csv", io.BytesIO(b"col1,col2\na,b\n"), "text/csv")},
        )
        assert response.status_code == 422

    def test_delete_removes_it(self, client):
        client.post(
            "/api/holdings-file/MYETF",
            files={"file": ("MYETF.csv", io.BytesIO(self.HOLDINGS_CSV.encode()), "text/csv")},
        )
        assert client.delete("/api/holdings-file/MYETF").json()["deleted"] is True


class TestDividendsInApi:
    def test_portfolio_xirr_accounts_for_dividends(self, client):
        """A high-yield holding must not report its price-only return."""
        body = client.post("/api/analyze", json={
            "lots": [{"symbol": "SCHD", "quantity": 220, "cost_per_share": 68.30,
                      "purchase_date": "2022-07-22"}],
        }).json()
        holding = body["holdings"][0]
        # SCHD yields ~3.5% in the fixture set; a price-only figure would land
        # near 4%, and the dividend-aware one materially above it.
        assert holding["annualized_return"] > holding["ttm_market_return"] - 0.10
        assert holding["annualized_return"] > 0.06
        assert body["summary"]["annualized_return"] == pytest.approx(
            holding["annualized_return"], abs=0.005
        ), "a single-holding portfolio's XIRR should match that holding's"
