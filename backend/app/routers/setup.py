"""3-step shed onboarding router (Owner -> Dynamic N Looms -> Data Seed/Clean)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.core import Loom, UnitSettings, User
from app.schemas.step1 import (
    AuthTokenResponse,
    SetupInitializeRequest,
    SetupStatusResponse,
    UserResponse,
)
from app.services.seed_defaults import (
    import_historical_seed,
    seed_default_tariff_and_stops,
    seed_optional_sample_data,
)

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status(db: Annotated[Session, Depends(get_db)]) -> SetupStatusResponse:
    """Return whether initial shed onboarding has been completed."""
    cfg = get_settings()
    settings_row = db.scalar(select(UnitSettings).limit(1))
    owner_exists = db.scalar(select(User.id).where(User.role == "OWNER").limit(1)) is not None
    loom_count = db.scalar(select(func.count(Loom.id))) or 0
    is_done = bool(settings_row and settings_row.setup_completed_at and owner_exists)
    db_url_name = Path(db.get_bind().url.database).name if db.get_bind().url.database else cfg.db_path.name
    return SetupStatusResponse(
        is_initialized=is_done,
        unit_name=settings_row.unit_name if settings_row else None,
        loom_count=int(loom_count),
        is_demo_mode=cfg.is_demo_active() or db_url_name.lower() == "loomos_demo.db",
        active_db_name=db_url_name,
    )


@router.get("/templates/{template_name}")
def download_onboarding_csv_template(template_name: str) -> Response:
    """Provide blank CSV templates for historical EB bills and deliveries."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    if template_name == "eb_bills":
        writer.writerow(["period_start", "period_end", "units_consumed", "net_bill_rs", "power_cut_mins", "notes"])
        writer.writerow(["2026-02-28", "2026-04-26", "6361", "32282.00", "120", "Sample format (replace row)"])
    elif template_name == "deliveries":
        writer.writerow(["delivery_date", "trader_name", "challan_no", "sort_name", "metres", "rate_rs_per_m"])
        writer.writerow(["2026-04-22", "Sri Murugan Textiles", "CH-041", "40s x 40s Grey", "6200.00", "6.00"])
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown CSV template")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="loomos_{template_name}_template.csv"'},
    )


@router.post("/initialize", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def initialize_shed(
    payload: SetupInitializeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokenResponse:
    """Atomically initialize Owner account, dynamic N looms, and optional historical/demo seed."""
    existing_settings = db.scalar(select(UnitSettings).limit(1))
    existing_owner = db.scalar(select(User.id).where(User.role == "OWNER").limit(1))
    if (existing_settings and existing_settings.setup_completed_at) or existing_owner is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LOOMOS is already initialized. Please sign in as Owner.",
        )

    # Step 1: Claim Shed -> Create Owner first so all subsequent records carry created_by
    owner = User(
        full_name=payload.owner_full_name.strip(),
        username=payload.owner_username.strip(),
        password_hash=hash_password(payload.owner_password),
        role="OWNER",
        preferred_lang=payload.default_language,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    record_audit(
        db,
        entity_type="user",
        entity_id=owner.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(owner, ["username", "role", "preferred_lang"]),
        reason="Initial Owner account created in Setup Step 1",
    )

    # Seed editable DB presets (TANGEDCO LA3A2 + standard Stop Reasons incl. Power Cut)
    tariff_plan = seed_default_tariff_and_stops(db, owner.id)

    unit = UnitSettings(
        unit_name=payload.unit_name.strip(),
        location=payload.location.strip(),
        default_language=payload.default_language,
        shifts_per_day=payload.shifts_per_day,
        planned_shift_mins=payload.planned_shift_mins,
        default_entry_mode=payload.default_entry_mode,
        active_tariff_plan_id=tariff_plan.id,
        setup_completed_at=datetime.now(timezone.utc),
    )
    db.add(unit)
    db.flush()

    # Step 2: Size Shed -> Generate dynamic N looms across requested groups
    seen_numbers: set[str] = set()
    for group in payload.loom_groups:
        for offset in range(group.count):
            num_val = group.start_number + offset
            loom_num = f"{group.prefix}{num_val:02d}"
            if loom_num in seen_numbers:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Duplicate generated loom number: {loom_num}",
                )
            seen_numbers.add(loom_num)
            db.add(
                Loom(
                    loom_number=loom_num,
                    loom_type=group.loom_type,
                    make_model=group.make_model.strip(),
                    rated_rpm=group.rated_rpm,
                    reed_space_in=group.reed_space_in,
                    cloth_width_in=group.cloth_width_in,
                    default_pick=group.default_pick,
                    status="OPERATIONAL",
                    is_active=True,
                    created_by=owner.id,
                )
            )

    # Step 3: Clean Start / CSV History Import / Clearly Labelled Sample Seed
    if payload.seed_mode == "CSV_IMPORT":
        import_historical_seed(
            db,
            owner_id=owner.id,
            tariff_plan=tariff_plan,
            eb_bills=payload.historical_eb_bills,
            deliveries=payload.historical_deliveries,
        )
    elif payload.seed_mode == "SAMPLE_DEMO":
        seed_optional_sample_data(db, owner_id=owner.id, tariff_plan=tariff_plan)

    db.commit()
    db.refresh(owner)

    token = create_access_token(owner.id, owner.username, owner.role)
    return AuthTokenResponse(access_token=token, user=UserResponse.model_validate(owner))
