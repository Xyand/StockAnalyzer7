"""Pydantic schemas shared by the API, the services and the importers."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AssetClass(str, Enum):
    EQUITY = "equity"
    BOND = "bond"
    CASH = "cash"
    COMMODITY = "commodity"
    REAL_ESTATE = "real_estate"
    CRYPTO = "crypto"
    DERIVATIVE = "derivative"
    OTHER = "other"


class SecurityType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    CASH = "cash"
    CRYPTO = "crypto"
    OTHER = "other"

    @property
    def is_fund(self) -> bool:
        return self in {SecurityType.ETF, SecurityType.MUTUAL_FUND}


# --------------------------------------------------------------------------
# Portfolio input
# --------------------------------------------------------------------------

class Lot(BaseModel):
    """A single purchase tranche. Multiple lots per symbol are supported so
    that money-weighted (XIRR) returns reflect the real cash-flow timeline."""

    symbol: str
    quantity: float
    cost_per_share: float | None = None
    purchase_date: date | None = None
    account: str | None = None
    currency: str | None = None
    note: str | None = None

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @property
    def cost_basis(self) -> float:
        return (self.cost_per_share or 0.0) * self.quantity


class Position(BaseModel):
    """All lots of one symbol, rolled up."""

    symbol: str
    quantity: float
    cost_basis: float
    lots: list[Lot] = Field(default_factory=list)
    account: str | None = None

    @property
    def average_cost(self) -> float | None:
        return self.cost_basis / self.quantity if self.quantity else None


class Portfolio(BaseModel):
    name: str = "My Portfolio"
    base_currency: str = "USD"
    lots: list[Lot] = Field(default_factory=list)
    #: Plain cash balances keyed by currency, held outside any security.
    cash: dict[str, float] = Field(default_factory=dict)

    def positions(self) -> list[Position]:
        by_symbol: dict[str, Position] = {}
        for lot in self.lots:
            pos = by_symbol.get(lot.symbol)
            if pos is None:
                pos = Position(symbol=lot.symbol, quantity=0.0, cost_basis=0.0, account=lot.account)
                by_symbol[lot.symbol] = pos
            pos.quantity += lot.quantity
            pos.cost_basis += lot.cost_basis
            pos.lots.append(lot)
        return sorted(by_symbol.values(), key=lambda p: p.symbol)


# --------------------------------------------------------------------------
# Market data
# --------------------------------------------------------------------------

class SecurityInfo(BaseModel):
    symbol: str
    name: str | None = None
    security_type: SecurityType = SecurityType.OTHER
    asset_class: AssetClass = AssetClass.OTHER
    currency: str = "USD"
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None


class Quote(BaseModel):
    symbol: str
    price: float
    currency: str = "USD"
    as_of: date | None = None


class PricePoint(BaseModel):
    date: date
    close: float
    #: Close adjusted for dividends and splits — the basis for total return.
    adj_close: float


class FundHolding(BaseModel):
    """One line of a fund's composition."""

    symbol: str | None = None
    name: str | None = None
    weight: float  # fraction of fund NAV, 0..1
    asset_class: AssetClass | None = None
    sector: str | None = None
    country: str | None = None

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        return v or None


class FundComposition(BaseModel):
    symbol: str
    holdings: list[FundHolding] = Field(default_factory=list)
    source: str = "unknown"
    as_of: date | None = None
    #: True when the source only publishes the largest N positions.
    partial: bool = False

    @property
    def covered_weight(self) -> float:
        return sum(h.weight for h in self.holdings)


# --------------------------------------------------------------------------
# Analysis output
# --------------------------------------------------------------------------

class YearReturn(BaseModel):
    year: int
    #: Total return of the security over that calendar year (price + dividends).
    market_return: float | None = None
    #: Return on the money actually invested that year, XIRR-based.
    position_return: float | None = None
    start_value: float | None = None
    end_value: float | None = None
    partial: bool = False


class HoldingAnalysis(BaseModel):
    symbol: str
    name: str | None = None
    security_type: SecurityType = SecurityType.OTHER
    asset_class: AssetClass = AssetClass.OTHER
    quantity: float
    price: float | None = None
    market_value: float | None = None
    cost_basis: float = 0.0
    unrealized_pl: float | None = None
    unrealized_pl_pct: float | None = None
    weight: float | None = None
    currency: str = "USD"

    #: Trailing-12-month total return of the security itself.
    ttm_market_return: float | None = None
    #: Total return of this position since the first purchase, not annualized.
    total_return_since_purchase: float | None = None
    #: Money-weighted annualized return of this position (XIRR).
    annualized_return: float | None = None
    holding_period_days: int | None = None
    yearly: list[YearReturn] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExposureRow(BaseModel):
    key: str
    label: str
    value: float
    weight: float
    #: Which of the user's tickers contribute, and how much.
    sources: dict[str, float] = Field(default_factory=dict)
    direct_value: float = 0.0
    indirect_value: float = 0.0
    asset_class: AssetClass | None = None
    sector: str | None = None
    country: str | None = None


class LookthroughReport(BaseModel):
    total_value: float
    resolved_value: float
    unresolved_value: float
    by_asset: list[ExposureRow] = Field(default_factory=list)
    by_asset_class: list[ExposureRow] = Field(default_factory=list)
    by_sector: list[ExposureRow] = Field(default_factory=list)
    by_country: list[ExposureRow] = Field(default_factory=list)
    fund_coverage: dict[str, float] = Field(default_factory=dict)
    fund_sources: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    scaled: bool = False


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    unrealized_pl: float
    unrealized_pl_pct: float | None
    base_currency: str
    holdings_count: int
    ttm_return: float | None = None
    annualized_return: float | None = None
    as_of: date | None = None


class AnalysisResponse(BaseModel):
    summary: PortfolioSummary
    holdings: list[HoldingAnalysis]
    years: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str = "unknown"


Granularity = Literal["asset", "asset_class", "sector", "country"]
