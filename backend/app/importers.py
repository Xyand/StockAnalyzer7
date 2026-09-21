"""Turn a broker CSV export — or a hand-written one — into a Portfolio.

Broker exports agree on nothing: column names, percent signs, currency
symbols, "Cost Basis" meaning per-share in one file and total in the next,
preamble and disclaimer rows above and below the real table. This importer
sniffs its way through all of that and reports what it could not read rather
than silently dropping rows.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .models import Lot, Portfolio

SYMBOL_COLUMNS = ("symbol", "ticker", "security", "securitysymbol", "instrument", "fund")
QUANTITY_COLUMNS = ("quantity", "shares", "qty", "units", "sharequantity", "position", "numberofshares")
UNIT_COST_COLUMNS = ("costpershare", "averagecost", "avgcost", "priceperhare", "unitcost",
                     "purchaseprice", "price", "avgpriceperhare", "averagecostbasis", "costbasispershare")
TOTAL_COST_COLUMNS = ("costbasis", "totalcost", "totalcostbasis", "bookvalue", "amountinvested", "cost")
DATE_COLUMNS = ("purchasedate", "dateacquired", "acquireddate", "tradedate", "date", "opendate", "buydate")
ACCOUNT_COLUMNS = ("account", "accountname", "accountnumber", "portfolio")
CURRENCY_COLUMNS = ("currency", "ccy", "tradecurrency")
NOTE_COLUMNS = ("note", "notes", "comment", "description")

CASH_SYMBOLS = {"CASH", "USD", "$$CASH", "CASH&CASHINVESTMENTS", "SPAXX**", "CORE**"}

_DATE_FORMATS = (
    "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d-%b-%Y", "%b %d, %Y",
    "%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M",
)

_NUMERIC = re.compile(r"-?[\d,]*\.?\d+")


@dataclass
class ImportResult:
    portfolio: Portfolio
    rows_read: int = 0
    rows_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (key or "").lower())


#: Roles in the order they claim columns. Cost-per-share is resolved before
#: total cost, because "costpershare" also prefix-matches "cost".
COLUMN_ROLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("symbol", SYMBOL_COLUMNS),
    ("quantity", QUANTITY_COLUMNS),
    ("date", DATE_COLUMNS),
    ("account", ACCOUNT_COLUMNS),
    ("currency", CURRENCY_COLUMNS),
    ("unit_cost", UNIT_COST_COLUMNS),
    ("total_cost", TOTAL_COST_COLUMNS),
    ("note", NOTE_COLUMNS),
)


def resolve_columns(fieldnames: list[str]) -> dict[str, str]:
    """Map each role to exactly one normalized column name.

    Exact matches are claimed first, then prefix matches, and a column already
    claimed by one role is never handed to another — otherwise a "Cost Per
    Share" column would also satisfy the "cost" (total) role and a $1.00
    unit price would be read as a $1.00 position.
    """
    keys = [_norm(f) for f in fieldnames if f]
    mapping: dict[str, str] = {}
    taken: set[str] = set()

    for role, candidates in COLUMN_ROLES:
        for candidate in candidates:
            if candidate in keys and candidate not in taken:
                mapping[role] = candidate
                taken.add(candidate)
                break

    for role, candidates in COLUMN_ROLES:
        if role in mapping:
            continue
        for key in keys:
            if key in taken:
                continue
            if any(key.startswith(candidate) for candidate in candidates):
                mapping[role] = key
                taken.add(key)
                break
    return mapping


def _get(row: dict[str, str], columns: dict[str, str], role: str) -> str | None:
    column = columns.get(role)
    if column is None:
        return None
    value = row.get(column)
    return value if value not in (None, "") else None


def parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"n/a", "na", "-", "--", "none"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    match = _NUMERIC.search(text.replace(",", ""))
    if not match:
        return None
    try:
        value = float(match.group().replace(",", ""))
    except ValueError:
        return None
    if negative or (text.lstrip().startswith("-")):
        value = -abs(value)
    return value


def parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _find_header(lines: list[str]) -> int:
    best_index, best_score = 0, -1
    for index, line in enumerate(lines[:30]):
        keys = {_norm(cell) for cell in next(csv.reader([line]), [])}
        score = 0
        if keys & set(SYMBOL_COLUMNS):
            score += 2
        if keys & set(QUANTITY_COLUMNS):
            score += 2
        if keys & (set(UNIT_COST_COLUMNS) | set(TOTAL_COST_COLUMNS)):
            score += 1
        if score > best_score:
            best_index, best_score = index, score
    return best_index if best_score >= 3 else 0


def import_portfolio_csv(
    text: str, name: str = "My Portfolio", base_currency: str = "USD"
) -> ImportResult:
    lines = [line for line in text.splitlines() if line.strip()]
    result = ImportResult(portfolio=Portfolio(name=name, base_currency=base_currency))
    if not lines:
        result.warnings.append("The file is empty.")
        return result

    header_index = _find_header(lines)
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    if not reader.fieldnames:
        result.warnings.append("No column headers found.")
        return result

    columns = resolve_columns(list(reader.fieldnames))
    if "symbol" not in columns:
        result.warnings.append(
            "No symbol/ticker column found. Expected one of: "
            + ", ".join(SYMBOL_COLUMNS[:4])
        )
        return result

    for line_number, raw_row in enumerate(reader, start=header_index + 2):
        row = {_norm(k): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k}
        symbol_raw = _get(row, columns, "symbol")
        if not symbol_raw:
            continue
        symbol = symbol_raw.strip().upper()
        result.rows_read += 1

        quantity = parse_number(_get(row, columns, "quantity"))
        unit_cost = parse_number(_get(row, columns, "unit_cost"))
        total_cost = parse_number(_get(row, columns, "total_cost"))

        if symbol.replace(" ", "") in CASH_SYMBOLS or symbol.startswith("CASH"):
            # A cash line carries its balance as a quantity of dollars, as a
            # quantity priced at 1.00, or as a total-cost figure.
            if quantity and unit_cost:
                amount = quantity * unit_cost
            elif quantity:
                amount = quantity
            else:
                amount = total_cost
            if amount:
                currency = (_get(row, columns, "currency") or base_currency).upper()
                result.portfolio.cash[currency] = result.portfolio.cash.get(currency, 0.0) + amount
            continue

        if not quantity:
            result.rows_skipped += 1
            result.warnings.append(f"Line {line_number} ({symbol}): no share quantity; row skipped.")
            continue

        if unit_cost is None and total_cost is not None and quantity:
            unit_cost = total_cost / quantity
        if unit_cost is None:
            result.warnings.append(
                f"Line {line_number} ({symbol}): no cost recorded. "
                "Profit and loss for this lot will be blank."
            )

        result.portfolio.lots.append(
            Lot(
                symbol=symbol,
                quantity=quantity,
                cost_per_share=unit_cost,
                purchase_date=parse_date(_get(row, columns, "date")),
                account=_get(row, columns, "account"),
                currency=_get(row, columns, "currency"),
                note=_get(row, columns, "note"),
            )
        )

    if not result.portfolio.lots and not result.portfolio.cash:
        result.warnings.append("No usable holdings were found in the file.")
    return result


def portfolio_to_csv(portfolio: Portfolio) -> str:
    """Round-trip export, in the canonical column layout."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["symbol", "quantity", "cost_per_share", "purchase_date", "account", "note"])
    for lot in portfolio.lots:
        writer.writerow([
            lot.symbol,
            lot.quantity,
            "" if lot.cost_per_share is None else lot.cost_per_share,
            lot.purchase_date.isoformat() if lot.purchase_date else "",
            lot.account or "",
            lot.note or "",
        ])
    for currency, amount in portfolio.cash.items():
        writer.writerow(["CASH", "", "", "", "", f"{amount} {currency}"])
    return buffer.getvalue()
