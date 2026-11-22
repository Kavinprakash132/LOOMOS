"""Pydantic v2 schemas for Build Step 1: Setup, Auth, Settings, Masters & Audit Logs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LoomType = Literal["SHUTTLE", "RAPIER", "AIRJET", "WATERJET", "PROJECTILE"]
LoomStatus = Literal["OPERATIONAL", "UNDER_MAINTENANCE", "IDLE"]
WageMode = Literal["PER_METRE", "PER_LOOM_SHIFT", "PER_SHIFT_ATTENDANCE", "FIXED_WEEKLY"]
WeaverRoleType = Literal["WEAVER", "PIRN_WINDER", "HELPER", "FITTER"]
UserRole = Literal["OWNER", "SUPERVISOR"]
LangCode = Literal["en", "ta"]
SlipLangCode = Literal["en", "ta", "hi"]
EntryMode = Literal["DIRECT", "COUNTER"]


class LoomGroupInput(BaseModel):
    """Defines a batch of looms generated during onboarding or bulk creation."""

    count: int = Field(ge=1, le=500)
    prefix: str = Field(default="L-", min_length=1, max_length=12)
    start_number: int = Field(default=1, ge=1, le=9999)
    loom_type: LoomType = "SHUTTLE"
    make_model: str = Field(default="", max_length=80)
    rated_rpm: int = Field(default=160, ge=40, le=2500)
    reed_space_in: int = Field(default=56, ge=20, le=220)


class HistoricalEbSeedRow(BaseModel):
    """Single historical EB bill row imported via CSV during Step 3 onboarding."""

    period_start: date
    period_end: date
    units_consumed: Decimal = Field(ge=0)
    net_bill_paise: int = Field(ge=0)
    total_power_cut_mins: int = Field(default=0, ge=0)
    notes: str | None = None


class HistoricalDeliverySeedRow(BaseModel):
    """Single historical delivery summary row imported via CSV during Step 3 onboarding."""

    trader_name: str = Field(min_length=1, max_length=120)
    challan_no: str = Field(min_length=1, max_length=60)
    delivery_date: date
    metres: Decimal = Field(gt=0)
    applied_rate_paise: int = Field(gt=0)
    sort_name: str | None = None


class SetupInitializeRequest(BaseModel):
    """3-step onboarding payload: Step 1 Owner & Unit -> Step 2 N Looms -> Step 3 Seed/Clean."""

    # Step 1: Claim Your Shed (Security & Ownership first)
    owner_full_name: str = Field(min_length=2, max_length=100)
    owner_username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.@-]+$")
    owner_password: str = Field(min_length=6, max_length=128)
    unit_name: str = Field(min_length=2, max_length=120)
    location: str = Field(default="", max_length=120)
    default_language: LangCode = "en"

    # Step 2: Size Your Shed (Dynamic N looms)
    loom_groups: list[LoomGroupInput] = Field(min_length=1)
    shifts_per_day: int = Field(default=2, ge=1, le=3)
    planned_shift_mins: int = Field(default=600, ge=60, le=1440)
    default_entry_mode: EntryMode = "DIRECT"

    # Step 3: Clean start, CSV history import, or clearly labelled sample seed
    seed_mode: Literal["CLEAN", "SAMPLE_DEMO", "CSV_IMPORT"] = "CLEAN"
    historical_eb_bills: list[HistoricalEbSeedRow] = Field(default_factory=list)
    historical_deliveries: list[HistoricalDeliverySeedRow] = Field(default_factory=list)


class SetupStatusResponse(BaseModel):
    is_initialized: bool
    unit_name: str | None = None
    loom_count: int = 0
    is_demo_mode: bool = False
    active_db_name: str = "loomos.db"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    username: str
    role: UserRole
    preferred_lang: LangCode
    is_active: bool
    ai_enabled: bool = False
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = "SUPERVISOR"
    preferred_lang: LangCode = "en"


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None
    preferred_lang: LangCode | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class LanguageUpdateRequest(BaseModel):
    preferred_lang: LangCode


class UnitSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_name: str
    location: str
    default_language: LangCode
    shifts_per_day: int
    planned_shift_mins: int
    shift_cutoff_hour: int
    default_entry_mode: EntryMode
    sanctioned_kw: Decimal
    active_tariff_plan_id: int | None
    setup_completed_at: datetime | None


class UnitSettingsUpdateRequest(BaseModel):
    unit_name: str | None = Field(default=None, min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    default_language: LangCode | None = None
    shifts_per_day: int | None = Field(default=None, ge=1, le=3)
    planned_shift_mins: int | None = Field(default=None, ge=60, le=1440)
    shift_cutoff_hour: int | None = Field(default=None, ge=0, le=23)
    default_entry_mode: EntryMode | None = None
    sanctioned_kw: Decimal | None = Field(default=None, gt=0)
    active_tariff_plan_id: int | None = None


class EbTariffSlabInput(BaseModel):
    min_unit: int = Field(ge=0)
    max_unit: int | None = Field(default=None, ge=1)
    rate_paise_per_unit: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_bounds(self) -> "EbTariffSlabInput":
        if self.max_unit is not None and self.max_unit <= self.min_unit:
            raise ValueError("max_unit must be greater than min_unit")
        return self


class EbTariffSlabResponse(EbTariffSlabInput):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EbTariffPlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    billing_cycle_days: int = Field(default=60, ge=1, le=365)
    overhead_per_kw_paise: int = Field(default=0, ge=0)
    fixed_charge_per_kw_month_paise: int = Field(default=0, ge=0)
    electricity_tax_bps: int = Field(default=500, ge=0, le=5000)
    fppca_paise_per_unit: int = Field(default=0, ge=0)
    tax_on_gross: bool = False
    effective_from: date
    notes: str | None = Field(default=None, max_length=255)
    slabs: list[EbTariffSlabInput] = Field(min_length=1)

    @field_validator("slabs")
    @classmethod
    def _sort_and_validate_slabs(cls, slabs: list[EbTariffSlabInput]) -> list[EbTariffSlabInput]:
        ordered = sorted(slabs, key=lambda s: s.min_unit)
        for idx in range(len(ordered) - 1):
            curr, nxt = ordered[idx], ordered[idx + 1]
            if curr.max_unit is None:
                raise ValueError("Only the highest slab may have an unbounded max_unit")
            if curr.max_unit > nxt.min_unit:
                raise ValueError("Tariff slabs cannot overlap")
        return ordered


class EbTariffPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    billing_cycle_days: int
    overhead_per_kw_paise: int
    fixed_charge_per_kw_month_paise: int
    electricity_tax_bps: int
    fppca_paise_per_unit: int
    tax_on_gross: bool
    effective_from: date
    notes: str | None
    is_deleted: bool
    slabs: list[EbTariffSlabResponse]


class StopReasonCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_]+$")
    label_en: str = Field(min_length=2, max_length=80)
    label_ta: str = Field(min_length=1, max_length=120)
    is_power_cut: bool = False


class StopReasonUpdate(BaseModel):
    label_en: str | None = Field(default=None, min_length=2, max_length=80)
    label_ta: str | None = Field(default=None, min_length=1, max_length=120)
    is_power_cut: bool | None = None
    is_active: bool | None = None


class StopReasonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label_en: str
    label_ta: str
    is_power_cut: bool
    is_active: bool


class LoomCreate(BaseModel):
    loom_number: str = Field(min_length=1, max_length=30)
    loom_type: LoomType = "SHUTTLE"
    make_model: str = Field(default="", max_length=80)
    rated_rpm: int = Field(default=160, ge=40, le=2500)
    reed_space_in: int = Field(default=56, ge=20, le=220)
    status: LoomStatus = "OPERATIONAL"


class LoomUpdate(BaseModel):
    loom_number: str | None = Field(default=None, min_length=1, max_length=30)
    loom_type: LoomType | None = None
    make_model: str | None = Field(default=None, max_length=80)
    rated_rpm: int | None = Field(default=None, ge=40, le=2500)
    reed_space_in: int | None = Field(default=None, ge=20, le=220)
    status: LoomStatus | None = None
    is_active: bool | None = None


class LoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    loom_number: str
    loom_type: LoomType
    make_model: str
    rated_rpm: int
    reed_space_in: int
    status: LoomStatus
    is_active: bool


class WageRuleCreate(BaseModel):
    wage_mode: WageMode
    rate_paise: int = Field(gt=0)
    effective_from: date


class WageRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weaver_id: int
    wage_mode: WageMode
    rate_paise: int
    effective_from: date
    effective_to: date | None
    is_deleted: bool


class WeaverCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    full_name_ta: str | None = Field(default=None, max_length=120)
    full_name_hi: str | None = Field(default=None, max_length=120)
    preferred_slip_lang: SlipLangCode = "en"
    role_type: WeaverRoleType = "WEAVER"
    phone: str = Field(default="", max_length=20)
    wage_mode: WageMode
    rate_paise: int = Field(gt=0)
    effective_from: date | None = None


class WeaverUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    full_name_ta: str | None = Field(default=None, max_length=120)
    full_name_hi: str | None = Field(default=None, max_length=120)
    preferred_slip_lang: SlipLangCode | None = None
    role_type: WeaverRoleType | None = None
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class WeaverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    full_name_ta: str | None
    full_name_hi: str | None
    preferred_slip_lang: SlipLangCode
    role_type: WeaverRoleType
    phone: str
    is_active: bool
    wage_rules: list[WageRuleResponse] = Field(default_factory=list)


class TraderCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    contact_name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=20)


class TraderUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=120)
    contact_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class TraderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    contact_name: str
    phone: str
    is_active: bool


class FabricSortCreate(BaseModel):
    sort_name: str = Field(min_length=2, max_length=120)
    warp_count: str = Field(default="", max_length=30)
    weft_count: str = Field(default="", max_length=30)
    reed: int = Field(gt=0)
    pick: int = Field(gt=0)
    width_in: Decimal = Field(gt=0)
    agreed_rate_paise: int = Field(gt=0)
    expected_weft_kg_per_100m: Decimal = Field(default=Decimal("0.000"), ge=0)
    wastage_pct: Decimal = Field(default=Decimal("2.50"), ge=0, le=50)


class FabricSortUpdate(BaseModel):
    sort_name: str | None = Field(default=None, min_length=2, max_length=120)
    warp_count: str | None = Field(default=None, max_length=30)
    weft_count: str | None = Field(default=None, max_length=30)
    reed: int | None = Field(default=None, gt=0)
    pick: int | None = Field(default=None, gt=0)
    width_in: Decimal | None = Field(default=None, gt=0)
    agreed_rate_paise: int | None = Field(default=None, gt=0)
    expected_weft_kg_per_100m: Decimal | None = Field(default=None, ge=0)
    wastage_pct: Decimal | None = Field(default=None, ge=0, le=50)
    is_active: bool | None = None


class FabricSortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sort_name: str
    warp_count: str
    weft_count: str
    reed: int
    pick: int
    width_in: Decimal
    agreed_rate_paise: int
    expected_weft_kg_per_100m: Decimal
    wastage_pct: Decimal
    is_active: bool


class SoftDeleteRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=255)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    action: str
    changed_by: int | None
    changed_at: datetime
    old_values_json: str | None
    new_values_json: str | None
    reason: str | None
