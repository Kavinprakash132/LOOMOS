"""Operational Floor Utilization/OEE and Owner Financial Dashboard router."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import User
from app.schemas.dashboard import FloorDashboardResponse, OwnerDashboardResponse
from app.services.dashboard_service import compute_floor_dashboard, compute_owner_financials

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _resolve_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    end = to_date or date.today()
    start = from_date or (end - timedelta(days=6))
    if end < start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="to_date must be >= from_date")
    return start, end


@router.get("/floor", response_model=FloorDashboardResponse)
def get_floor_dashboard(
    from_date: date | None = None,
    to_date: date | None = None,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> FloorDashboardResponse:
    """Operational metrics (Availability, Performance, A*P Utilization, conditional OEE) for Owner/Supervisor."""
    start, end = _resolve_range(from_date, to_date)
    data = compute_floor_dashboard(db, period_start=start, period_end=end)
    return FloorDashboardResponse.model_validate(data)


@router.get("/summary", response_model=OwnerDashboardResponse)
def get_owner_dashboard_summary(
    from_date: date | None = None,
    to_date: date | None = None,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> OwnerDashboardResponse:
    """Owner-only full Dashboard including P&L, receivables, and Rate-Cut totals."""
    start, end = _resolve_range(from_date, to_date)
    floor = compute_floor_dashboard(db, period_start=start, period_end=end)
    fin = compute_owner_financials(db, period_start=start, period_end=end)
    floor["financials"] = fin
    return OwnerDashboardResponse.model_validate(floor)
