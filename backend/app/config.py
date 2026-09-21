"""Application configuration.

Everything is env-overridable so the same code runs against live market data
on a laptop and against checked-in fixtures in CI / offline sandboxes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass
class Settings:
    #: "yahoo" for live data via yfinance, "fixtures" for the offline dataset.
    market_data_provider: str = field(
        default_factory=lambda: os.environ.get("SA_PROVIDER", "yahoo").strip().lower()
    )
    #: Fall back to fixtures when the live provider raises (blocked network, rate limit).
    fallback_to_fixtures: bool = field(
        default_factory=lambda: _env_bool("SA_FALLBACK_FIXTURES", True)
    )
    data_dir: Path = field(default_factory=lambda: _env_path("SA_DATA_DIR", REPO_ROOT / "data"))
    db_path: Path = field(default_factory=lambda: _env_path("SA_DB_PATH", REPO_ROOT / "data" / "portfolio.db"))
    #: Seconds a cached quote/history/holdings entry stays fresh.
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.environ.get("SA_CACHE_TTL", "3600"))
    )
    #: How deep to recurse when an ETF holds other funds (VT -> VTI -> AAPL).
    max_lookthrough_depth: int = field(
        default_factory=lambda: int(os.environ.get("SA_MAX_DEPTH", "4"))
    )
    #: Allow fetching public holdings files straight from issuer websites.
    allow_issuer_downloads: bool = field(
        default_factory=lambda: _env_bool("SA_ISSUER_DOWNLOADS", True)
    )
    base_currency: str = field(default_factory=lambda: os.environ.get("SA_BASE_CCY", "USD").upper())

    @property
    def fixtures_dir(self) -> Path:
        return self.data_dir / "fixtures"

    @property
    def etf_holdings_dir(self) -> Path:
        return self.data_dir / "etf_holdings"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.cache_dir.mkdir(parents=True, exist_ok=True)
        _settings.etf_holdings_dir.mkdir(parents=True, exist_ok=True)
    return _settings


def reset_settings() -> None:
    """Test hook: force re-read of the environment."""
    global _settings
    _settings = None
