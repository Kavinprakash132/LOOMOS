"""API routes for Phase 3 Analytics, Phase 4 Excel/Statement Reports & Phase 5 Expansion Simulator."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import today_ist
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import User
from app.services.analytics_service import (
    build_full_xlsx_workbook,
    build_printable_statement,
    calculate_custom_eb_bill,
    compute_beam_etas,
    compute_eb_prediction_and_outage_loss,
    compute_eb_vs_metres_efficiency,
    compute_production_anomalies,
    compute_weekly_forecast,
    estimate_eb_for_metres,
    simulate_expansion,
)

router = APIRouter(prefix="/api/v1", tags=["analytics-and-reports"])


@router.get("/analytics/overview")
def get_analytics_overview(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Return Beam Finish ETAs, EB Predictor + Outage Loss, EB-vs-Metres Efficiency, MAD/IQR Anomalies, and 5-Week Forecast."""
    return {
        "beam_etas": compute_beam_etas(db),
        "eb_prediction": compute_eb_prediction_and_outage_loss(db),
        "eb_efficiency": compute_eb_vs_metres_efficiency(db),
        "anomalies": compute_production_anomalies(db),
        "weekly_forecast": compute_weekly_forecast(db),
    }


@router.get("/analytics/eb-estimate")
def get_eb_estimate_for_metres(
    metres: float = Query(ge=0, le=10_000_000),
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Estimate bi-monthly EB units and itemized TNPDCL bill for a target metres woven."""
    return estimate_eb_for_metres(db, metres)


@router.get("/analytics/eb-calculate")
def get_custom_eb_bill_calculation(
    units_kwh: float = Query(ge=0, le=10_000_000),
    sanctioned_kw: float | None = Query(default=None, gt=0, le=5000),
    billing_days: int | None = Query(default=None, ge=1, le=366),
    recorded_demand_kw: float | None = Query(default=None, ge=0, le=5000),
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Interactive TNPDCL-style EB bill calculator with slab working sheet using active DB tariff."""
    return calculate_custom_eb_bill(
        db,
        units_kwh=units_kwh,
        sanctioned_kw=sanctioned_kw,
        billing_days=billing_days,
        recorded_demand_kw=recorded_demand_kw,
    )


@router.get("/analytics/expansion-default")
def get_default_expansion_simulation(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Default 20 / 30 / 50 / 100 shuttle loom expansion simulation."""
    return simulate_expansion(db, {"loom_count": 20})


@router.post("/analytics/expansion-simulate")
def post_expansion_simulation(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    """Run deterministic multi-size loom expansion P&L, EMI, payback, and 2D sensitivity check."""
    return simulate_expansion(db, payload)


@router.get("/analytics/reports/statement")
def get_printable_statement(
    from_date: date | None = None,
    to_date: date | None = None,
    trader_id: int | None = None,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Return Monthly P&L & Trader Account Statement data for HTML Print / PDF."""
    end = to_date or today_ist()
    start = from_date or (end - timedelta(days=29))
    if end < start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="to_date must be >= from_date")
    return build_printable_statement(db, from_date=start, to_date=end, trader_id=trader_id)


@router.get("/exports/xlsx/workbook")
def download_full_excel_workbook(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Download formatted Excel workbook (.xlsx)."""
    data = build_full_xlsx_workbook(db)
    filename = f"loomos_full_report_{today_ist().isoformat()}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
