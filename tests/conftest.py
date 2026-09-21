import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Every test runs against the checked-in offline dataset so the suite never
# depends on a live market data feed.
os.environ.setdefault("SA_PROVIDER", "fixtures")
os.environ.setdefault("SA_ISSUER_DOWNLOADS", "0")

import pytest  # noqa: E402

from backend.app.config import reset_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Point the cache, database and uploaded-holdings directories at tmp_path
    so tests never touch the developer's real data directory."""
    monkeypatch.setenv("SA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SA_CACHE_TTL", "0")
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def market_data():
    from backend.app.providers import MarketData

    return MarketData()


@pytest.fixture
def sample_portfolio():
    from backend.app.importers import import_portfolio_csv

    csv_text = (REPO_ROOT / "data" / "sample_portfolio.csv").read_text()
    return import_portfolio_csv(csv_text).portfolio
