"""Pydantic v2 schemas for Build Step 2: Beams, Weft, Shifts, Attendance, Payroll, Finance & Exports."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.step1 import EntryMode, SlipLangCode, WageMode, WeaverRoleType

BeamStatus = Literal["IN_STOCK", "RUNNING", "COMPLETED"]
UnloadReason = Literal["COMPLETED", "PARTIAL_UNLOAD", "TRANSFER"]
AttendanceStatus = Literal["PRESENT", "HALF", "ABSENT"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "DISMISSED"]


# ---------------------------------------------------------------------------
# Shed Calendar
# ---------------------------------------------------------------------------
class CalendarDayUpsert(BaseModel):
    is_working_day: bool = True
    planned_shifts: int = Field(default=2, ge=0, le=3)
    note: str | None = Field(default=None, max_length=255)


class CalendarDayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    calendar_date: date
    is_working_day: bool
    planned_shifts: int
    note: str | None


# ---------------------------------------------------------------------------
# Beams, Loom Loading & Weft Yarn Wastage
# ---------------------------------------------------------------------------
class BeamCreate(BaseModel):
    beam_no: str = Field(min_length=1, max_length=50)
    trader_id: int
    sort_id: int
    received_date: date
    warp_length_m: Decimal = Field(gt=0)
    opening_woven_m: Decimal = Field(default=Decimal("0.00"), ge=0)
    expected_tail_waste_m: Decimal = Field(default=Decimal("0.00"), ge=0)
    due_date: date | None = None
    expected_pieces: int | None = Field(default=None, ge=1)


class BeamUpdate(BaseModel):
    opening_woven_m: Decimal | None = Field(default=None, ge=0)
    expected_tail_waste_m: Decimal | None = Field(default=None, ge=0)
    returned_weft_kg: Decimal | None = Field(default=None, ge=0)
    actual_waste_m: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None
    expected_pieces: int | None = Field(default=None, ge=1)


class BeamLoadRequest(BaseModel):
    loom_id: int
    loaded_at: datetime | None = None


class BeamUnloadRequest(BaseModel):
    unload_reason: UnloadReason = "COMPLETED"
    unloaded_at: datetime | None = None
    returned_weft_kg: Decimal | None = Field(default=None, ge=0)
    actual_waste_m: Decimal | None = Field(default=None, ge=0)


class WeftReceiptCreate(BaseModel):
    beam_id: int | None = None
    trader_id: int | None = None
    sort_id: int | None = None
    received_date: date
    bags: int = Field(default=1, ge=1)
    net_weight_kg: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _require_beam_or_trader(self) -> "WeftReceiptCreate":
        if self.beam_id is None and self.trader_id is None:
            raise ValueError("Provide either beam_id or trader_id for weft receipt")
        return self


class WeftReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    beam_id: int | None
    trader_id: int | None
    sort_id: int | None
    received_date: date
    bags: int
    net_weight_kg: Decimal
    note: str | None
    is_deleted: bool


class BeamResponse(BaseModel):
    id: int
    beam_no: str
    trader_id: int
    trader_name: str
    sort_id: int
    sort_name: str
    received_date: date
    warp_length_m: Decimal
    opening_woven_m: Decimal
    expected_tail_waste_m: Decimal
    returned_weft_kg: Decimal
    actual_waste_m: Decimal | None
    due_date: date | None
    expected_pieces: int | None
    status: BeamStatus
    active_loom_id: int | None = None
    active_loom_number: str | None = None
    woven_m: Decimal
    usable_total_m: Decimal
    remaining_m: Decimal
    progress_pct: float
    weft_received_kg: Decimal
    weft_consumed_kg: Decimal
    expected_weft_kg: Decimal
    actual_wastage_pct: float | None = None
    allowed_wastage_pct: float
    wastage_flagged: bool = False


# ---------------------------------------------------------------------------
# Daily Shifts & Worker Attendance
# ---------------------------------------------------------------------------
class ShiftRowInput(BaseModel):
    client_uuid: str = Field(min_length=4, max_length=64)
    loom_id: int
    weaver_id: int
    beam_id: int | None = None
    entry_mode: EntryMode = "DIRECT"
    start_meter: Decimal | None = Field(default=None, ge=0)
    end_meter: Decimal | None = Field(default=None, ge=0)
    net_metres: Decimal | None = Field(default=None, ge=0)
    planned_mins: int | None = Field(default=None, gt=0, le=1440)
    power_cut_mins: int = Field(default=0, ge=0, le=1440)
    downtime_mins: int = Field(default=0, ge=0, le=1440)
    defective_metres: Decimal = Field(default=Decimal("0.00"), ge=0)
    stop_reason_id: int | None = None
    notes: str | None = Field(default=None, max_length=255)
    meter_reset: bool = False


class ShiftBatchSaveRequest(BaseModel):
    entry_date: date
    shift_no: int = Field(ge=1, le=3)
    rows: list[ShiftRowInput] = Field(min_length=1)


class ShiftEntryUpdate(BaseModel):
    weaver_id: int | None = None
    beam_id: int | None = None
    entry_mode: EntryMode | None = None
    start_meter: Decimal | None = Field(default=None, ge=0)
    end_meter: Decimal | None = Field(default=None, ge=0)
    net_metres: Decimal | None = Field(default=None, ge=0)
    planned_mins: int | None = Field(default=None, gt=0, le=1440)
    power_cut_mins: int | None = Field(default=None, ge=0, le=1440)
    downtime_mins: int | None = Field(default=None, ge=0, le=1440)
    defective_metres: Decimal | None = Field(default=None, ge=0)
    stop_reason_id: int | None = None
    notes: str | None = Field(default=None, max_length=255)


class ShiftEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_uuid: str
    loom_id: int
    loom_number: str | None = None
    weaver_id: int
    weaver_name: str | None = None
    beam_id: int | None
    beam_no: str | None = None
    entry_date: date
    shift_no: int
    entry_mode: EntryMode
    start_meter: Decimal | None
    end_meter: Decimal | None
    net_metres: Decimal
    planned_mins: int
    power_cut_mins: int
    downtime_mins: int
    defective_metres: Decimal
    stop_reason_id: int | None
    notes: str | None
    is_deleted: bool


class LoomPrefillRow(BaseModel):
    loom_id: int
    loom_number: str
    loom_type: str
    rated_rpm: int
    default_weaver_id: int | None = None
    active_beam_id: int | None = None
    active_beam_no: str | None = None
    active_sort_name: str | None = None
    remaining_beam_m: Decimal | None = None
    last_end_meter: Decimal | None = None
    existing_entries: list[ShiftEntryResponse] = Field(default_factory=list)


class ShiftPrefillResponse(BaseModel):
    suggested_date: date
    suggested_shift: int
    entry_date: date
    shift_no: int
    shifts_per_day: int = 2
    planned_shift_mins: int
    default_entry_mode: EntryMode
    looms: list[LoomPrefillRow]


class AttendanceItemInput(BaseModel):
    weaver_id: int
    status: AttendanceStatus = "PRESENT"
    note: str | None = Field(default=None, max_length=255)


class AttendanceBatchRequest(BaseModel):
    attendance_date: date
    shift_no: int = Field(ge=1, le=3)
    items: list[AttendanceItemInput] = Field(min_length=1)


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weaver_id: int
    weaver_name: str | None = None
    attendance_date: date
    shift_no: int
    status: AttendanceStatus
    note: str | None
    is_deleted: bool


# ---------------------------------------------------------------------------
# Advances & 4-Mode Payroll
# ---------------------------------------------------------------------------
class AdvanceCreate(BaseModel):
    weaver_id: int
    advance_date: date
    amount_paise: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class AdvanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weaver_id: int
    weaver_name: str | None = None
    advance_date: date
    amount_paise: int
    note: str | None
    is_deleted: bool


class PayslipCalculateRequest(BaseModel):
    period_start: date
    period_end: date
    weaver_ids: list[int] | None = None
    deduct_period_advances: bool = True
    defect_deductions_paise: dict[int, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_dates(self) -> "PayslipCalculateRequest":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self


class PayslipLinePreview(BaseModel):
    weaver_id: int
    weaver_name: str
    full_name_ta: str | None
    full_name_hi: str | None
    preferred_slip_lang: SlipLangCode
    role_type: WeaverRoleType
    wage_mode: WageMode
    units_worked: Decimal
    rate_paise: int
    gross_paise: int
    advance_deducted_paise: int
    defect_deduction_paise: int
    net_payable_paise: int
    rule_breakdown: list[dict[str, Any]] = Field(default_factory=list)


class PayslipFinalizeItem(BaseModel):
    weaver_id: int
    wage_mode_snapshot: WageMode
    units_worked: Decimal = Field(ge=0)
    rate_paise_snapshot: int = Field(gt=0)
    gross_paise: int = Field(ge=0)
    advance_deducted_paise: int = Field(default=0, ge=0)
    defect_deduction_paise: int = Field(default=0, ge=0)


class PayslipFinalizeRequest(BaseModel):
    period_start: date
    period_end: date
    items: list[PayslipFinalizeItem] = Field(min_length=1)


class PayslipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weaver_id: int
    weaver_name: str | None = None
    preferred_slip_lang: SlipLangCode = "en"
    period_start: date
    period_end: date
    wage_mode_snapshot: WageMode
    units_worked: Decimal
    rate_paise_snapshot: int
    gross_paise: int
    advance_deducted_paise: int
    defect_deduction_paise: int
    net_payable_paise: int
    status: str
    is_deleted: bool


class PrintablePayslipResponse(BaseModel):
    payslip: PayslipResponse
    unit_name: str
    unit_location: str
    lang: SlipLangCode
    localized_weaver_name: str
    role_type: WeaverRoleType
    labels: dict[str, str]
    printed_on: date


# ---------------------------------------------------------------------------
# Deliveries, Trader Payments, Expenses, EB Bills & Alerts
# ---------------------------------------------------------------------------
class DeliveryItemInput(BaseModel):
    beam_id: int | None = None
    sort_id: int | None = None
    pieces: int = Field(default=1, ge=1)
    metres: Decimal = Field(gt=0)
    applied_rate_paise: int = Field(gt=0)
    production_start_date: date | None = None
    production_end_date: date | None = None
    is_opening_stock: bool = False


class DeliveryCreate(BaseModel):
    trader_id: int
    challan_no: str = Field(min_length=1, max_length=60)
    delivery_date: date
    items: list[DeliveryItemInput] = Field(min_length=1)


class DeliveryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    beam_id: int | None
    sort_id: int | None
    sort_name: str | None = None
    agreed_rate_paise: int | None = None
    pieces: int
    metres: Decimal
    applied_rate_paise: int
    underpayment_paise: int = 0
    production_start_date: date | None
    production_end_date: date | None
    is_opening_stock: bool


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trader_id: int
    trader_name: str | None = None
    challan_no: str
    delivery_date: date
    total_metres: Decimal
    source: str
    is_deleted: bool
    total_amount_paise: int = 0
    total_underpayment_paise: int = 0
    has_rate_cut: bool = False
    items: list[DeliveryItemResponse] = Field(default_factory=list)


class TraderPaymentCreate(BaseModel):
    trader_id: int
    payment_date: date
    amount_paise: int = Field(ge=0)
    shortage_deduction_paise: int = Field(default=0, ge=0)
    reference: str | None = Field(default=None, max_length=120)


class TraderPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trader_id: int
    trader_name: str | None = None
    payment_date: date
    amount_paise: int
    shortage_deduction_paise: int
    reference: str | None
    is_deleted: bool


class TraderLedgerSummary(BaseModel):
    trader_id: int
    company_name: str
    total_metres: Decimal
    billed_paise: int
    received_paise: int
    shortage_paise: int
    balance_paise: int
    underpayment_paise: int


class ExpenseCreate(BaseModel):
    expense_date: date
    category: str = Field(min_length=2, max_length=60)
    amount_paise: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_date: date
    category: str
    amount_paise: int
    note: str | None
    is_deleted: bool


class EbReadingCreate(BaseModel):
    reading_date: date
    kwh_total: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=255)


class EbReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reading_date: date
    kwh_total: Decimal
    note: str | None
    is_deleted: bool


class EbBillCreate(BaseModel):
    tariff_plan_id: int | None = None
    period_start: date
    period_end: date
    units_consumed: Decimal = Field(ge=0)
    energy_paise: int | None = Field(default=None, ge=0)
    fixed_paise: int | None = Field(default=None, ge=0)
    tax_paise: int | None = Field(default=None, ge=0)
    fppca_paise: int | None = Field(default=None, ge=0)
    subsidy_paise: int = Field(default=0, ge=0)
    other_charges_paise: int = Field(default=0, ge=0)
    net_bill_paise: int = Field(ge=0)
    total_power_cut_mins: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=255)


class EbBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tariff_plan_id: int | None
    period_start: date
    period_end: date
    units_consumed: Decimal
    energy_paise: int
    fixed_paise: int
    tax_paise: int
    fppca_paise: int
    subsidy_paise: int
    other_charges_paise: int
    overhead_paise: int
    net_bill_paise: int
    total_power_cut_mins: int
    notes: str | None
    is_deleted: bool


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    loom_id: int | None
    severity: str
    message: str
    status: AlertStatus
    created_at: datetime


class AlertUpdate(BaseModel):
    status: AlertStatus
