"""SQLAlchemy 2 ORM models for LOOMOS v3 (3NF, soft deletes, immutable audit log)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampAuditMixin:
    """Common creation/modification audit columns."""

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class SoftDeleteMixin:
    """Soft-delete fields required on all financial records."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class User(Base):
    """Authenticated owner and supervisor accounts."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # OWNER | SUPERVISOR
    preferred_lang: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("role IN ('OWNER', 'SUPERVISOR')", name="ck_users_role"),
        CheckConstraint("preferred_lang IN ('en', 'ta')", name="ck_users_lang"),
    )


class AuditLog(Base):
    """Immutable append-only audit trail for financial and configuration changes."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATE|UPDATE|SOFT_DELETE|FINALIZE
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    old_values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EbTariffPlan(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Editable electricity tariff plan with component rates (zero hardcoded values)."""

    __tablename__ = "eb_tariff_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_cycle_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    overhead_per_kw_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    fixed_charge_per_kw_month_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    electricity_tax_bps: Mapped[int] = mapped_column(Integer, default=500, nullable=False)  # 500 = 5.00%
    fppca_paise_per_unit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_on_gross: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    slabs: Mapped[list["EbTariffSlab"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="EbTariffSlab.min_unit"
    )


class EbTariffSlab(Base):
    """Unit-range slab inside an EB tariff plan."""

    __tablename__ = "eb_tariff_slabs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("eb_tariff_plans.id", ondelete="CASCADE"), nullable=False)
    min_unit: Mapped[int] = mapped_column(Integer, nullable=False)
    max_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = unbounded upper slab
    rate_paise_per_unit: Mapped[int] = mapped_column(Integer, nullable=False)

    plan: Mapped[EbTariffPlan] = relationship(back_populates="slabs")

    __table_args__ = (
        CheckConstraint("min_unit >= 0", name="ck_eb_slab_min"),
        CheckConstraint("rate_paise_per_unit >= 0", name="ck_eb_slab_rate"),
    )


class UnitSettings(Base):
    """Global shed configuration established during Step 1 onboarding and editable later."""

    __tablename__ = "unit_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    default_language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    shifts_per_day: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    planned_shift_mins: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    shift_cutoff_hour: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    default_entry_mode: Mapped[str] = mapped_column(String(10), default="DIRECT", nullable=False)
    sanctioned_kw: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("10.00"), nullable=False)
    active_tariff_plan_id: Mapped[int | None] = mapped_column(ForeignKey("eb_tariff_plans.id"), nullable=True)
    setup_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("default_language IN ('en', 'ta')", name="ck_unit_lang"),
        CheckConstraint("shifts_per_day BETWEEN 1 AND 3", name="ck_unit_shifts"),
        CheckConstraint("planned_shift_mins > 0", name="ck_unit_planned_mins"),
        CheckConstraint("default_entry_mode IN ('DIRECT', 'COUNTER')", name="ck_unit_entry_mode"),
    )


class ShedCalendar(Base, TimestampAuditMixin):
    """Working-day / holiday / planned-shift overrides for accurate ETA and capacity forecasting."""

    __tablename__ = "shed_calendar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    is_working_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    planned_shifts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (CheckConstraint("planned_shifts BETWEEN 0 AND 3", name="ck_cal_planned_shifts"),)


class Loom(Base, TimestampAuditMixin):
    """Individual weaving loom (dynamic N-loom registry; soft-archived via is_active)."""

    __tablename__ = "looms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loom_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    loom_type: Mapped[str] = mapped_column(String(20), default="SHUTTLE", nullable=False)
    make_model: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    rated_rpm: Mapped[int] = mapped_column(Integer, default=160, nullable=False)
    reed_space_in: Mapped[int] = mapped_column(Integer, default=56, nullable=False)
    cloth_width_in: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    default_pick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(25), default="OPERATIONAL", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("loom_type IN ('SHUTTLE', 'RAPIER', 'AIRJET', 'WATERJET', 'PROJECTILE')", name="ck_loom_type"),
        CheckConstraint("status IN ('OPERATIONAL', 'UNDER_MAINTENANCE', 'IDLE')", name="ck_loom_status"),
        CheckConstraint("rated_rpm > 0", name="ck_loom_rpm"),
    )


class Weaver(Base, TimestampAuditMixin):
    """Weavers, winders/helpers, and fitters (soft-archived via is_active)."""

    __tablename__ = "weavers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name_ta: Mapped[str | None] = mapped_column(String(120), nullable=True)
    full_name_hi: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_slip_lang: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    role_type: Mapped[str] = mapped_column(String(20), default="WEAVER", nullable=False)
    phone: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    wage_rules: Mapped[list["WageRule"]] = relationship(
        back_populates="weaver", order_by="WageRule.effective_from.desc()"
    )

    __table_args__ = (
        CheckConstraint("role_type IN ('WEAVER', 'PIRN_WINDER', 'HELPER', 'FITTER')", name="ck_weaver_role_type"),
        CheckConstraint("preferred_slip_lang IN ('en', 'ta', 'hi')", name="ck_weaver_slip_lang"),
    )


class WeaverAttendance(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Daily shift attendance for helpers, fitters, and zero-loom weaver shifts."""

    __tablename__ = "weaver_attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weaver_id: Mapped[int] = mapped_column(ForeignKey("weavers.id"), nullable=False, index=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(15), default="PRESENT", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("shift_no BETWEEN 1 AND 3", name="ck_att_shift_no"),
        CheckConstraint("status IN ('PRESENT', 'HALF', 'ABSENT')", name="ck_att_status"),
        Index(
            "uq_active_att_weaver_date_shift",
            "weaver_id",
            "attendance_date",
            "shift_no",
            unique=True,
            sqlite_where=text("is_deleted = 0"),
        ),
    )


class WageRule(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Dated wage rule per weaver/helper so rate revisions preserve historical payslips."""

    __tablename__ = "wage_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weaver_id: Mapped[int] = mapped_column(ForeignKey("weavers.id"), nullable=False, index=True)
    wage_mode: Mapped[str] = mapped_column(String(25), nullable=False)
    rate_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    weaver: Mapped[Weaver] = relationship(back_populates="wage_rules")

    __table_args__ = (
        CheckConstraint(
            "wage_mode IN ('PER_METRE', 'PER_LOOM_SHIFT', 'PER_SHIFT_ATTENDANCE', 'FIXED_WEEKLY')",
            name="ck_wage_mode",
        ),
        CheckConstraint("rate_paise > 0", name="ck_wage_rate_pos"),
    )


class Trader(Base, TimestampAuditMixin):
    """Job-work client / master weaver supplying warp beams and weft yarn."""

    __tablename__ = "traders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class FabricSort(Base, TimestampAuditMixin):
    """Fabric construction specification, agreed conversion rate, and weft consumption baseline."""

    __tablename__ = "fabric_sorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sort_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    warp_count: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    weft_count: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    reed: Mapped[int] = mapped_column(Integer, nullable=False)
    pick: Mapped[int] = mapped_column(Integer, nullable=False)
    width_in: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    agreed_rate_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_weft_kg_per_100m: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=Decimal("0.000"), nullable=False)
    wastage_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("2.50"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("agreed_rate_paise > 0", name="ck_sort_rate_pos"),
        CheckConstraint("wastage_pct >= 0", name="ck_sort_wastage"),
    )


class Beam(Base, TimestampAuditMixin):
    """Sized warp beam received from a trader."""

    __tablename__ = "beams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    beam_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False, index=True)
    sort_id: Mapped[int] = mapped_column(ForeignKey("fabric_sorts.id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    warp_length_m: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    opening_woven_m: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    expected_tail_waste_m: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    returned_weft_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"), nullable=False)
    actual_waste_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    expected_pieces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="IN_STOCK", nullable=False)

    __table_args__ = (
        CheckConstraint("warp_length_m > 0", name="ck_beam_len_pos"),
        CheckConstraint("opening_woven_m >= 0", name="ck_beam_opening_nonneg"),
        CheckConstraint("expected_tail_waste_m >= 0", name="ck_beam_tail_waste_nonneg"),
        CheckConstraint("returned_weft_kg >= 0", name="ck_beam_ret_weft_nonneg"),
        CheckConstraint("status IN ('IN_STOCK', 'RUNNING', 'COMPLETED')", name="ck_beam_status"),
    )


class WeftReceipt(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Weft yarn bags/kg received for a beam or trader stock."""

    __tablename__ = "weft_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    beam_id: Mapped[int | None] = mapped_column(ForeignKey("beams.id"), nullable=True, index=True)
    trader_id: Mapped[int | None] = mapped_column(ForeignKey("traders.id"), nullable=True, index=True)
    sort_id: Mapped[int | None] = mapped_column(ForeignKey("fabric_sorts.id"), nullable=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    bags: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    net_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("net_weight_kg > 0", name="ck_weft_kg_pos"),
        CheckConstraint("beam_id IS NOT NULL OR trader_id IS NOT NULL", name="ck_weft_beam_or_trader"),
    )


class BeamLoading(Base, TimestampAuditMixin):
    """Tracks mounting and unmounting of a warp beam onto a loom."""

    __tablename__ = "beam_loadings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loom_id: Mapped[int] = mapped_column(ForeignKey("looms.id"), nullable=False, index=True)
    beam_id: Mapped[int] = mapped_column(ForeignKey("beams.id"), nullable=False, index=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unload_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    __table_args__ = (
        Index(
            "uq_active_beam_per_loom",
            "loom_id",
            unique=True,
            sqlite_where=text("unloaded_at IS NULL"),
        ),
    )


class StopReason(Base, TimestampAuditMixin):
    """Configurable stoppage reasons including explicit power-cut classification."""

    __tablename__ = "stop_reasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    label_en: Mapped[str] = mapped_column(String(80), nullable=False)
    label_ta: Mapped[str] = mapped_column(String(120), nullable=False)
    is_power_cut: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ShiftEntry(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Per-loom shift production record with unique client_uuid for offline-sync readiness."""

    __tablename__ = "shift_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_uuid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    loom_id: Mapped[int] = mapped_column(ForeignKey("looms.id"), nullable=False, index=True)
    weaver_id: Mapped[int] = mapped_column(ForeignKey("weavers.id"), nullable=False, index=True)
    beam_id: Mapped[int | None] = mapped_column(ForeignKey("beams.id"), nullable=True, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_no: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_mode: Mapped[str] = mapped_column(String(10), default="DIRECT", nullable=False)
    start_meter: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    end_meter: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    net_metres: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    planned_mins: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    power_cut_mins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    downtime_mins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    defective_metres: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    stop_reason_id: Mapped[int | None] = mapped_column(ForeignKey("stop_reasons.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("shift_no BETWEEN 1 AND 3", name="ck_shift_no"),
        CheckConstraint("net_metres >= 0", name="ck_shift_metres_nonneg"),
        CheckConstraint("planned_mins > 0", name="ck_shift_planned_pos"),
        CheckConstraint("power_cut_mins >= 0", name="ck_shift_powercut_nonneg"),
        CheckConstraint("downtime_mins >= 0", name="ck_shift_downtime_nonneg"),
        CheckConstraint("defective_metres >= 0", name="ck_shift_defective_nonneg"),
        Index(
            "uq_active_shift_loom_date_shift_beam",
            "loom_id",
            "entry_date",
            "shift_no",
            "beam_id",
            unique=True,
            sqlite_where=text("is_deleted = 0 AND beam_id IS NOT NULL"),
        ),
        Index(
            "uq_active_shift_loom_date_shift_nobeam",
            "loom_id",
            "entry_date",
            "shift_no",
            unique=True,
            sqlite_where=text("is_deleted = 0 AND beam_id IS NULL"),
        ),
    )


class Advance(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Cash advance (uthaav) paid to a weaver or helper."""

    __tablename__ = "advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weaver_id: Mapped[int] = mapped_column(ForeignKey("weavers.id"), nullable=False, index=True)
    advance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_advance_pos"),)


class Payslip(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Calculated weaver/helper payout snapshot (soft-deletable, never hard deleted)."""

    __tablename__ = "payslips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weaver_id: Mapped[int] = mapped_column(ForeignKey("weavers.id"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    wage_mode_snapshot: Mapped[str] = mapped_column(String(25), nullable=False)
    units_worked: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rate_paise_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gross_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    advance_deducted_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    defect_deduction_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    net_payable_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="FINALIZED", nullable=False)

    __table_args__ = (CheckConstraint("status IN ('DRAFT', 'FINALIZED')", name="ck_payslip_status"),)


class Delivery(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Grey cloth delivery challan dispatched to a trader."""

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False, index=True)
    challan_no: Mapped[str] = mapped_column(String(60), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_metres: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="MANUAL", nullable=False)


class DeliveryItem(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Line item inside a trader delivery with rate verification against fabric sort."""

    __tablename__ = "delivery_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), nullable=False, index=True)
    beam_id: Mapped[int | None] = mapped_column(ForeignKey("beams.id"), nullable=True)
    sort_id: Mapped[int | None] = mapped_column(ForeignKey("fabric_sorts.id"), nullable=True)
    pieces: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metres: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    applied_rate_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    production_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    production_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_opening_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (CheckConstraint("metres > 0", name="ck_delivery_item_m_pos"),)


class TraderPayment(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Payment received from a trader."""

    __tablename__ = "trader_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), nullable=False, index=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shortage_deduction_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

    __table_args__ = (CheckConstraint("amount_paise >= 0", name="ck_payment_nonneg"),)


class Inspection(Base, TimestampAuditMixin):
    """Fabric photo inspection storing every reviewed photo (both Defect and Clean)."""

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loom_id: Mapped[int | None] = mapped_column(ForeignKey("looms.id"), nullable=True, index=True)
    beam_id: Mapped[int | None] = mapped_column(ForeignKey("beams.id"), nullable=True)
    weaver_id: Mapped[int | None] = mapped_column(ForeignKey("weavers.id"), nullable=True)
    shift_entry_id: Mapped[int | None] = mapped_column(ForeignKey("shift_entries.id"), nullable=True)
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    heatmap_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    reviewed_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    second_reviewer_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    defective_metres: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    session_burst_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    split_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_reference_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('PENDING', 'CONFIRMED_DEFECT', 'CONFIRMED_CLEAN')",
            name="ck_inspection_review_status",
        ),
        CheckConstraint("defective_metres >= 0", name="ck_inspection_defective_nonneg"),
    )


class DefectPrediction(Base):
    """Model inference output tied to an Inspection record."""

    __tablename__ = "defect_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(60), nullable=False)
    predicted_label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    threshold_used: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_uncertain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    inference_ms: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)


class EbReading(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Intermediate EB meter snapshot for mid-cycle slab projections."""

    __tablename__ = "eb_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reading_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kwh_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EbBill(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Official bi-monthly electricity bill with itemized components and tracked power-cut duration."""

    __tablename__ = "eb_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tariff_plan_id: Mapped[int | None] = mapped_column(ForeignKey("eb_tariff_plans.id"), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    units_consumed: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    energy_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fixed_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tax_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    fppca_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    subsidy_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    other_charges_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    overhead_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    net_bill_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_power_cut_mins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Expense(Base, TimestampAuditMixin, SoftDeleteMixin):
    """Operational shed expenses (spares, oil, repairs, rent)."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Alert(Base):
    """Actionable dismissible alerts (rate underpayment, weft wastage, z-score/IQR, EB slab)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    loom_id: Mapped[int | None] = mapped_column(ForeignKey("looms.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(15), default="WARN", nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'ACKNOWLEDGED', 'DISMISSED')", name="ck_alert_status"),
    )


class AiChatThread(Base):
    """Private per-owner LOOMOS AI Copilot conversation thread (auto-pruned, scrubbed from demo backups)."""

    __tablename__ = "ai_chat_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False, index=True
    )

    messages: Mapped[list["AiChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="AiChatMessage.id",
    )


class AiChatMessage(Base):
    """Individual text message inside a private LOOMOS AI Copilot thread (images are never stored in DB)."""

    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("ai_chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    has_image: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(60), nullable=True)
    tools_used_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    thread: Mapped["AiChatThread"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_chat_msg_role"),
    )
