"""HTTP API."""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..config import get_settings
from ..importers import import_portfolio_csv, portfolio_to_csv
from ..models import AnalysisResponse, LookthroughReport, Portfolio
from ..providers import get_market_data, parse_holdings_csv
from ..services.analyzer import PortfolioAnalyzer
from ..services.exposure import build_report, concentration
from ..services.lookthrough import LookthroughEngine
from ..storage import DEFAULT_NAME, PortfolioStore

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_store: PortfolioStore | None = None


def store() -> PortfolioStore:
    global _store
    if _store is None:
        _store = PortfolioStore(get_settings().db_path)
    return _store


# --------------------------------------------------------------------------
# Request/response bodies
# --------------------------------------------------------------------------

class SavePortfolioRequest(BaseModel):
    portfolio: Portfolio
    name: str = DEFAULT_NAME


class ImportResponse(BaseModel):
    portfolio: Portfolio
    rows_read: int
    rows_skipped: int
    warnings: list[str] = Field(default_factory=list)


class LookthroughResponse(BaseModel):
    report: LookthroughReport
    top10_concentration: float
    provider: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    degraded: bool
    notes: list[str] = Field(default_factory=list)
    base_currency: str
    holdings_files: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    md = get_market_data()
    return HealthResponse(
        status="ok",
        provider=md.active_provider,
        degraded=md.degraded,
        notes=md.notes,
        base_currency=settings.base_currency,
        holdings_files=md.files.available_symbols(),
    )


@router.post("/portfolio/import", response_model=ImportResponse)
async def import_portfolio(file: UploadFile = File(...)) -> ImportResponse:
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is larger than 8 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    result = import_portfolio_csv(text, name=file.filename or "Imported portfolio")
    if not result.portfolio.lots and not result.portfolio.cash:
        raise HTTPException(
            status_code=422,
            detail="; ".join(result.warnings) or "No holdings could be read from that file.",
        )
    return ImportResponse(
        portfolio=result.portfolio,
        rows_read=result.rows_read,
        rows_skipped=result.rows_skipped,
        warnings=result.warnings,
    )


@router.post("/portfolio/save")
def save_portfolio(request: SavePortfolioRequest) -> dict:
    store().save(request.portfolio, request.name)
    return {"saved": True, "name": request.name}


@router.get("/portfolio", response_model=Portfolio | None)
def load_portfolio(name: str = DEFAULT_NAME) -> Portfolio | None:
    return store().load(name)


@router.get("/portfolio/list")
def list_portfolios() -> list[dict]:
    return store().list_names()


@router.delete("/portfolio")
def delete_portfolio(name: str = Query(...)) -> dict:
    return {"deleted": store().delete(name)}


@router.get("/portfolio/export")
def export_portfolio(name: str = DEFAULT_NAME) -> dict:
    portfolio = store().load(name)
    if portfolio is None:
        raise HTTPException(status_code=404, detail=f"No saved portfolio named '{name}'.")
    return {"filename": f"{name}.csv", "csv": portfolio_to_csv(portfolio)}


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(portfolio: Portfolio = Body(...), as_of: date | None = None) -> AnalysisResponse:
    if not portfolio.lots:
        raise HTTPException(status_code=422, detail="The portfolio has no holdings.")
    md = get_market_data(fresh=True)
    return PortfolioAnalyzer(md).analyze(portfolio, today=as_of)


@router.post("/lookthrough", response_model=LookthroughResponse)
def lookthrough(
    portfolio: Portfolio = Body(...),
    scale_to_full: bool = Query(
        False,
        description="Pro-rate each fund's undisclosed tail across its known holdings "
        "instead of reporting it as a separate bucket.",
    ),
    max_depth: int | None = Query(None, ge=1, le=6),
) -> LookthroughResponse:
    if not portfolio.lots:
        raise HTTPException(status_code=422, detail="The portfolio has no holdings.")

    md = get_market_data(fresh=True)
    analysis = PortfolioAnalyzer(md).analyze(portfolio)
    holdings = [
        (h.symbol, h.market_value) for h in analysis.holdings if h.market_value
    ]
    if not holdings:
        raise HTTPException(
            status_code=422,
            detail="None of the holdings could be priced, so there is nothing to break down.",
        )

    engine = LookthroughEngine(md, max_depth=max_depth)
    result = engine.expand(holdings, scale_to_full=scale_to_full)
    report = build_report(result, scaled=scale_to_full)
    report.warnings = analysis.warnings + report.warnings
    return LookthroughResponse(
        report=report,
        top10_concentration=concentration(report.by_asset),
        provider=analysis.provider,
    )


@router.post("/holdings-file/{symbol}")
async def upload_holdings_file(symbol: str, file: UploadFile = File(...)) -> dict:
    """Register a fund's full holdings CSV, downloaded from its issuer."""
    symbol = symbol.strip().upper()
    raw = await file.read()
    if len(raw) > 16 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is larger than 16 MB.")
    text = raw.decode("utf-8-sig", errors="replace")

    composition = parse_holdings_csv(text, symbol, f"upload:{file.filename}")
    if composition is None:
        raise HTTPException(
            status_code=422,
            detail="Could not find weight and name/ticker columns in that file.",
        )

    settings = get_settings()
    destination = settings.etf_holdings_dir / f"{symbol}.csv"
    destination.write_text(text)
    get_market_data(fresh=True)  # drop the cached composition
    return {
        "symbol": symbol,
        "holdings": len(composition.holdings),
        "covered_weight": round(composition.covered_weight, 4),
        "partial": composition.partial,
        "stored_at": str(destination),
    }


@router.delete("/holdings-file/{symbol}")
def delete_holdings_file(symbol: str) -> dict:
    path = get_settings().etf_holdings_dir / f"{symbol.strip().upper()}.csv"
    existed = path.exists()
    path.unlink(missing_ok=True)
    get_market_data(fresh=True)
    return {"deleted": existed}


@router.post("/cache/clear")
def clear_cache() -> dict:
    return {"removed": get_market_data().cache.clear()}


@router.get("/sample-portfolio", response_model=Portfolio)
def sample_portfolio() -> Portfolio:
    """The demo portfolio shipped in data/sample_portfolio.csv."""
    path = get_settings().data_dir / "sample_portfolio.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No sample portfolio is installed.")
    result = import_portfolio_csv(path.read_text(), name="Sample portfolio")
    return result.portfolio


@router.get("/symbols")
def known_symbols() -> dict:
    """Symbols available in the offline dataset — used by the demo picker."""
    md = get_market_data()
    return {"symbols": md.known_symbols(), "provider": md.active_provider}
