"""Provider interface plus the symbol heuristics shared by all providers."""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..models import AssetClass, FundComposition, PricePoint, Quote, SecurityInfo, SecurityType


class ProviderError(RuntimeError):
    """Raised when a provider cannot answer — network blocked, unknown symbol."""


@runtime_checkable
class MarketDataProvider(Protocol):
    name: str

    def get_info(self, symbol: str) -> SecurityInfo: ...

    def get_quote(self, symbol: str) -> Quote: ...

    def get_history(self, symbol: str, start: date, end: date) -> list[PricePoint]: ...

    def get_fund_composition(self, symbol: str) -> FundComposition | None: ...


# --------------------------------------------------------------------------
# Classification helpers
# --------------------------------------------------------------------------

_BOND_HINTS = (
    "bond", "treasury", "aggregate", "fixed income", "gilt", "tips", "municipal",
    "credit", "corporate debt", "government",
)
_COMMODITY_HINTS = ("gold", "silver", "commodity", "oil", "natural gas", "metal", "bullion")
_REIT_HINTS = ("reit", "real estate", "property")
_CRYPTO_HINTS = ("bitcoin", "ethereum", "crypto", "blockchain trust")
_CASH_HINTS = ("money market", "cash", "t-bill", "treasury bill", "repurchase", "repo")

_QUOTE_TYPE_MAP = {
    "EQUITY": SecurityType.STOCK,
    "ETF": SecurityType.ETF,
    "MUTUALFUND": SecurityType.MUTUAL_FUND,
    "CRYPTOCURRENCY": SecurityType.CRYPTO,
    "CURRENCY": SecurityType.CASH,
    "INDEX": SecurityType.OTHER,
    "FUTURE": SecurityType.OTHER,
}


def map_quote_type(quote_type: str | None) -> SecurityType:
    if not quote_type:
        return SecurityType.OTHER
    return _QUOTE_TYPE_MAP.get(quote_type.strip().upper(), SecurityType.OTHER)


def infer_asset_class(
    name: str | None,
    security_type: SecurityType = SecurityType.OTHER,
    sector: str | None = None,
) -> AssetClass:
    """Best-effort asset-class tagging from a security's name and metadata.

    Deliberately conservative: anything we cannot place stays OTHER rather than
    being silently folded into equity, so the look-through report can show it.
    """
    if security_type is SecurityType.CRYPTO:
        return AssetClass.CRYPTO
    if security_type is SecurityType.CASH:
        return AssetClass.CASH

    haystack = f"{name or ''} {sector or ''}".lower()
    for hints, klass in (
        (_CASH_HINTS, AssetClass.CASH),
        (_CRYPTO_HINTS, AssetClass.CRYPTO),
        (_BOND_HINTS, AssetClass.BOND),
        (_REIT_HINTS, AssetClass.REAL_ESTATE),
        (_COMMODITY_HINTS, AssetClass.COMMODITY),
    ):
        if any(hint in haystack for hint in hints):
            return klass

    if sector and sector.strip().lower() == "real estate":
        return AssetClass.REAL_ESTATE
    if security_type is SecurityType.STOCK:
        return AssetClass.EQUITY
    if security_type.is_fund:
        # A fund with no bond/commodity signal is overwhelmingly an equity fund;
        # look-through will correct this from the actual constituents anyway.
        return AssetClass.EQUITY
    return AssetClass.OTHER
