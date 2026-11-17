"""Pydantic v2 schemas for Phase 1 Operational Dashboard, Partial OEE & Financial Summary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.step2 import AlertResponse


class LoomOeeRow(BaseModel):
    loom_id: int
    loom_number: str
    loom_type: str
    rated_rpm: int
    sort_name: str | None = None
    shifts_logged: int
    net_metres: Decimal
    ideal_metres: Decimal | None = None
    planned_mins: int
    operating_mins: int
    power_cut_mins: int
    downtime_mins: int
    confirmed_defective_metres: Decimal
    availability_pct: float | None = None
    performance_pct: float | None = None
    utilization_ap_pct: float | None = None
    quality_pct: float | None = None
    full_oee_pct: float | None = None


class FloorDashboardResponse(BaseModel):
    period_start: date
    period_end: date
    today_date: date
    today_metres: Decimal
    period_metres: Decimal
    active_looms_count: int
    operational_looms_count: int
    running_beams_count: int
    weft_wastage_alerts_count: int
    total_planned_mins: int
    total_operating_mins: int
    total_power_cut_mins: int
    total_downtime_mins: int
    total_ideal_metres: Decimal
    confirmed_defective_metres: Decimal
    availability_pct: float | None = None
    performance_pct: float | None = None
    utilization_ap_pct: float | None = None
    quality_recorded: bool = False
    quality_pct: float | None = None
    full_oee_pct: float | None = None
    oee_note: str
    open_alerts: list[AlertResponse]
    loom_breakdown: list[LoomOeeRow]


class OwnerFinancialSummary(BaseModel):
    billed_revenue_paise: int
    finalized_wages_paise: int
    eb_bills_paise: int
    expenses_paise: int
    net_operating_paise: int
    total_receivable_paise: int
    total_rate_underpayment_paise: int


class OwnerDashboardResponse(FloorDashboardResponse):
    financials: OwnerFinancialSummary
