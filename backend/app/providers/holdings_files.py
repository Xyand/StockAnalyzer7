"""Full ETF/mutual-fund compositions from CSV files.

Free quote APIs publish only a fund's top ten positions, which covers perhaps
a third of a broad-market fund. Every major issuer, however, publishes the
*complete* holdings list as a CSV on its own website. Drop those files in
``data/etf_holdings/<SYMBOL>.csv`` — or register a URL in
``data/etf_holdings/sources.json`` — and look-through becomes exact.

Parsing is deliberately forgiving: issuer CSVs differ in column names, in how
many preamble lines they carry, and in whether weights are percents or
fractions.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import date
from pathlib import Path

from ..models import AssetClass, FundComposition, FundHolding
from .base import infer_asset_class

log = logging.getLogger(__name__)

SYMBOL_COLUMNS = ("ticker", "symbol", "holdingticker", "identifier", "localticker", "sedolticker")
NAME_COLUMNS = ("name", "securityname", "holdingname", "description", "issuername", "company")
WEIGHT_COLUMNS = (
    "weight", "weightpct", "weight(%)", "percentofnetassets", "%ofnetassets",
    "portfolioweight", "marketvaluepercent", "holdingpercent", "allocation", "%weight",
)
ASSET_CLASS_COLUMNS = ("assetclass", "asset_class", "securitytype", "sectype")
SECTOR_COLUMNS = ("sector", "gicssector", "industrygroup")
COUNTRY_COLUMNS = ("location", "country", "domicile", "countryofrisk")

_NON_TICKER = re.compile(r"^[-—–\s]*$")

ASSET_CLASS_ALIASES = {
    "equity": AssetClass.EQUITY,
    "stock": AssetClass.EQUITY,
    "common stock": AssetClass.EQUITY,
    "fixed income": AssetClass.BOND,
    "bond": AssetClass.BOND,
    "government bond": AssetClass.BOND,
    "corporate bond": AssetClass.BOND,
    "cash": AssetClass.CASH,
    "cash and/or derivatives": AssetClass.CASH,
    "money market": AssetClass.CASH,
    "commodity": AssetClass.COMMODITY,
    "real estate": AssetClass.REAL_ESTATE,
    "reit": AssetClass.REAL_ESTATE,
    "crypto": AssetClass.CRYPTO,
    "futures": AssetClass.DERIVATIVE,
    "derivative": AssetClass.DERIVATIVE,
}


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9%()]", "", (key or "").lower())


def _pick(row: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    return None


def _parse_weight(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace("%", "").replace(",", "").replace("$", "")
    if not text or text in {"-", "--", "N/A", "n/a"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value


def _find_header_row(lines: list[str]) -> int:
    """Issuer CSVs bury the real header under a fund-info preamble."""
    best_index, best_score = 0, -1
    for index, line in enumerate(lines[:40]):
        keys = {_normalize_key(cell) for cell in next(csv.reader([line]), [])}
        score = 0
        if keys & set(SYMBOL_COLUMNS):
            score += 2
        if keys & set(NAME_COLUMNS):
            score += 1
        if keys & set(WEIGHT_COLUMNS):
            score += 2
        if score > best_score:
            best_index, best_score = index, score
    return best_index if best_score >= 2 else 0


def parse_holdings_csv(text: str, symbol: str, source: str) -> FundComposition | None:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    header_index = _find_header_row(lines)
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))

    holdings: list[FundHolding] = []
    for raw_row in reader:
        row = {_normalize_key(k): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k}
        weight = _parse_weight(_pick(row, WEIGHT_COLUMNS))
        if weight is None:
            continue
        ticker = _pick(row, SYMBOL_COLUMNS)
        if ticker and _NON_TICKER.match(ticker):
            ticker = None
        name = _pick(row, NAME_COLUMNS)
        if not ticker and not name:
            continue

        raw_class = (_pick(row, ASSET_CLASS_COLUMNS) or "").strip().lower()
        asset_class = ASSET_CLASS_ALIASES.get(raw_class)
        sector = _pick(row, SECTOR_COLUMNS)
        if asset_class is None and (sector or name):
            inferred = infer_asset_class(name, sector=sector)
            asset_class = inferred if inferred is not AssetClass.OTHER else None

        holdings.append(
            FundHolding(
                symbol=ticker,
                name=name,
                weight=weight,
                asset_class=asset_class,
                sector=sector,
                country=_pick(row, COUNTRY_COLUMNS),
            )
        )

    if not holdings:
        return None

    total = sum(h.weight for h in holdings)
    if total > 1.5:  # the file used percents
        for holding in holdings:
            holding.weight /= 100.0
        total /= 100.0

    # Issuer files list every position, so anything under ~97% means the file
    # is truncated or carries non-weight rows we skipped.
    return FundComposition(
        symbol=symbol,
        holdings=holdings,
        source=source,
        partial=total < 0.97,
        as_of=date.today(),
    )


class HoldingsFileProvider:
    """Reads ``data/etf_holdings/<SYMBOL>.csv`` and registered issuer URLs."""

    name = "holdings-files"

    def __init__(self, directory: Path, allow_downloads: bool = True) -> None:
        self.directory = directory
        self.allow_downloads = allow_downloads
        self.directory.mkdir(parents=True, exist_ok=True)

    def _sources(self) -> dict[str, str]:
        path = self.directory / "sources.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            log.warning("sources.json is not valid JSON; ignoring it")
            return {}
        return {str(k).upper(): str(v) for k, v in data.items() if isinstance(v, str)}

    def local_path(self, symbol: str) -> Path | None:
        for candidate in (f"{symbol}.csv", f"{symbol.lower()}.csv", f"{symbol.replace('-', '.')}.csv"):
            path = self.directory / candidate
            if path.exists():
                return path
        return None

    def available_symbols(self) -> list[str]:
        local = {p.stem.upper() for p in self.directory.glob("*.csv")}
        return sorted(local | set(self._sources()))

    def get_fund_composition(self, symbol: str) -> FundComposition | None:
        path = self.local_path(symbol)
        if path is not None:
            try:
                return parse_holdings_csv(
                    path.read_text(encoding="utf-8-sig", errors="replace"), symbol, f"file:{path.name}"
                )
            except OSError as exc:
                log.warning("Could not read %s: %s", path, exc)

        url = self._sources().get(symbol.upper())
        if url and self.allow_downloads:
            return self._download(symbol, url)
        return None

    def _download(self, symbol: str, url: str) -> FundComposition | None:
        try:
            import httpx  # noqa: PLC0415 - lazy so offline mode needs no network stack
        except ImportError:
            return None
        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
        except Exception as exc:
            log.warning("Could not download holdings for %s from %s: %s", symbol, url, exc)
            return None

        composition = parse_holdings_csv(response.text, symbol, f"url:{url}")
        if composition is not None:
            # Cache it on disk so the next run works offline.
            try:
                (self.directory / f"{symbol}.csv").write_text(response.text)
            except OSError:
                pass
        return composition
