"""CSV exports (UTF-8 BOM for Excel), post-setup CSV historical imports, and SQLite hot backup."""

from __future__ import annotations

import csv
import io
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit
from app.core.config import get_settings, today_ist
from app.core.database import get_db
from app.core.security import require_owner
from app.models.core import (
    Advance,
    AuditLog,
    Beam,
    Delivery,
    EbBill,
    EbReading,
    EbTariffPlan,
    Expense,
    Payslip,
    ShiftEntry,
    UnitSettings,
    User,
)
from app.schemas.step1 import HistoricalDeliverySeedRow, HistoricalEbSeedRow
from app.services.seed_defaults import import_historical_seed

router = APIRouter(prefix="/api/v1", tags=["exports-backup"])


MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB CSV cap


def _sanitize_csv_cell(val: object) -> object:
    """Prevent Excel CSV formula injection (=, +, -, @, tab, CR) on text fields."""
    if not isinstance(val, str) or not val:
        return val
    if val[0] in ("=", "+", "-", "@", "\t", "\r"):
        # Allow legitimate negative numbers like "-12.50"
        if val[0] == "-":
            try:
                Decimal(val)
                return val
            except InvalidOperation:
                pass
        return f"'{val}"
    return val


def _csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    """Encode CSV with UTF-8 BOM (utf-8-sig) so Excel opens Tamil/Hindi and Rupee symbols cleanly."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows([[_sanitize_csv_cell(c) for c in row] for row in rows])
    payload = buf.getvalue().encode("utf-8-sig")
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exports/csv/{entity}")
def export_entity_csv(
    entity: str,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    today_tag = today_ist().isoformat()
    if entity == "shifts":
        items = db.scalars(select(ShiftEntry).where(ShiftEntry.is_deleted.is_(False)).order_by(ShiftEntry.entry_date.desc())).all()
        return _csv_response(
            f"loomos_shifts_{today_tag}.csv",
            ["id", "entry_date", "shift_no", "loom_id", "weaver_id", "beam_id", "entry_mode", "net_metres", "planned_mins", "power_cut_mins", "downtime_mins", "defective_metres", "client_uuid"],
            [
                [x.id, x.entry_date, x.shift_no, x.loom_id, x.weaver_id, x.beam_id, x.entry_mode, x.net_metres, x.planned_mins, x.power_cut_mins, x.downtime_mins, x.defective_metres, x.client_uuid]
                for x in items
            ],
        )
    if entity == "beams":
        items = db.scalars(select(Beam).order_by(Beam.received_date.desc())).all()
        return _csv_response(
            f"loomos_beams_{today_tag}.csv",
            ["id", "beam_no", "trader_id", "sort_id", "received_date", "warp_length_m", "opening_woven_m", "expected_tail_waste_m", "returned_weft_kg", "due_date", "status"],
            [
                [x.id, x.beam_no, x.trader_id, x.sort_id, x.received_date, x.warp_length_m, x.opening_woven_m, x.expected_tail_waste_m, x.returned_weft_kg, x.due_date, x.status]
                for x in items
            ],
        )
    if entity == "payslips":
        items = db.scalars(select(Payslip).where(Payslip.is_deleted.is_(False)).order_by(Payslip.period_end.desc())).all()
        return _csv_response(
            f"loomos_payslips_{today_tag}.csv",
            ["id", "weaver_id", "period_start", "period_end", "wage_mode", "units_worked", "rate_rs", "gross_rs", "advance_deducted_rs", "defect_deduction_rs", "net_payable_rs", "status"],
            [
                [x.id, x.weaver_id, x.period_start, x.period_end, x.wage_mode_snapshot, x.units_worked, f"{x.rate_paise_snapshot/100:.2f}", f"{x.gross_paise/100:.2f}", f"{x.advance_deducted_paise/100:.2f}", f"{x.defect_deduction_paise/100:.2f}", f"{x.net_payable_paise/100:.2f}", x.status]
                for x in items
            ],
        )
    if entity == "advances":
        items = db.scalars(select(Advance).where(Advance.is_deleted.is_(False)).order_by(Advance.advance_date.desc())).all()
        return _csv_response(
            f"loomos_advances_{today_tag}.csv",
            ["id", "weaver_id", "advance_date", "amount_rs", "note"],
            [[x.id, x.weaver_id, x.advance_date, f"{x.amount_paise/100:.2f}", x.note or ""] for x in items],
        )
    if entity == "deliveries":
        items = db.scalars(select(Delivery).where(Delivery.is_deleted.is_(False)).order_by(Delivery.delivery_date.desc())).all()
        return _csv_response(
            f"loomos_deliveries_{today_tag}.csv",
            ["id", "trader_id", "challan_no", "delivery_date", "total_metres", "source"],
            [[x.id, x.trader_id, x.challan_no, x.delivery_date, x.total_metres, x.source] for x in items],
        )
    if entity == "expenses":
        items = db.scalars(select(Expense).where(Expense.is_deleted.is_(False)).order_by(Expense.expense_date.desc())).all()
        return _csv_response(
            f"loomos_expenses_{today_tag}.csv",
            ["id", "expense_date", "category", "amount_rs", "note"],
            [[x.id, x.expense_date, x.category, f"{x.amount_paise/100:.2f}", x.note or ""] for x in items],
        )
    if entity == "eb_bills":
        items = db.scalars(select(EbBill).where(EbBill.is_deleted.is_(False)).order_by(EbBill.period_end.desc())).all()
        return _csv_response(
            f"loomos_eb_bills_{today_tag}.csv",
            ["id", "period_start", "period_end", "units_consumed", "energy_rs", "fixed_rs", "tax_rs", "fppca_rs", "net_bill_rs", "power_cut_mins", "notes"],
            [
                [x.id, x.period_start, x.period_end, x.units_consumed, f"{x.energy_paise/100:.2f}", f"{x.fixed_paise/100:.2f}", f"{x.tax_paise/100:.2f}", f"{x.fppca_paise/100:.2f}", f"{x.net_bill_paise/100:.2f}", x.total_power_cut_mins, x.notes or ""]
                for x in items
            ],
        )
    if entity == "eb_readings":
        items = db.scalars(select(EbReading).where(EbReading.is_deleted.is_(False)).order_by(EbReading.reading_date.desc())).all()
        return _csv_response(
            f"loomos_eb_readings_{today_tag}.csv",
            ["id", "reading_date", "kwh_total", "note"],
            [[x.id, x.reading_date, x.kwh_total, x.note or ""] for x in items],
        )
    if entity == "audit_logs":
        items = db.scalars(select(AuditLog).order_by(AuditLog.changed_at.desc()).limit(2000)).all()
        cfg = get_settings()
        redact = not cfg.is_ai_allowed_user(owner) and bool(cfg.ai_allowed_username_set())
        priv_ids = (
            {u.id for u in db.scalars(select(User)).all() if u.username.strip().lower() in cfg.ai_allowed_username_set()}
            if redact
            else set()
        )
        rows_out = []
        for x in items:
            if redact and x.entity_type == "user" and x.entity_id in priv_ids:
                continue
            c_by = None if (redact and x.changed_by in priv_ids) else x.changed_by
            reason = "Owner update" if (redact and x.reason and "AI Copilot" in x.reason) else (x.reason or "")
            rows_out.append(
                [x.id, x.entity_type, x.entity_id, x.action, c_by, x.changed_at.isoformat(), x.old_values_json or "", x.new_values_json or "", reason]
            )
        return _csv_response(
            f"loomos_audit_logs_{today_tag}.csv",
            ["id", "entity_type", "entity_id", "action", "changed_by", "changed_at", "old_values_json", "new_values_json", "reason"],
            rows_out,
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unsupported export entity: {entity}")


@router.post("/imports/eb-bills-csv")
async def import_eb_bills_csv(
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> dict[str, int]:
    """Import historical EB bills CSV after initial setup."""
    raw_bytes = await file.read(MAX_CSV_UPLOAD_BYTES + 1)
    if len(raw_bytes) > MAX_CSV_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="CSV file too large (max 5 MB)")
    try:
        raw = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(raw))
    rows: list[HistoricalEbSeedRow] = []
    for row_num, line in enumerate(reader, start=2):
        if not line.get("period_start") or not line.get("units_consumed"):
            continue
        try:
            net_paise = int(
                (Decimal(line["net_bill_rs"].strip()) * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            rows.append(
                HistoricalEbSeedRow(
                    period_start=date.fromisoformat(line["period_start"].strip()),
                    period_end=date.fromisoformat(line["period_end"].strip()),
                    units_consumed=Decimal(line["units_consumed"].strip()),
                    net_bill_paise=net_paise,
                    total_power_cut_mins=int(line.get("power_cut_mins") or 0),
                    notes=line.get("notes") or None,
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid EB CSV row {row_num}: {exc}",
            ) from exc
    settings = db.scalar(select(UnitSettings).limit(1))
    plan = (
        db.scalar(
            select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).where(
                EbTariffPlan.id == settings.active_tariff_plan_id
            )
        )
        if settings and settings.active_tariff_plan_id
        else None
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active EB tariff plan configured")

    import_historical_seed(db, owner_id=owner.id, tariff_plan=plan, eb_bills=rows, deliveries=[])
    db.commit()
    return {"imported_eb_bills": len(rows)}


@router.post("/imports/deliveries-csv")
async def import_deliveries_csv(
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> dict[str, int]:
    """Import historical weekly deliveries CSV after initial setup."""
    raw_bytes = await file.read(MAX_CSV_UPLOAD_BYTES + 1)
    if len(raw_bytes) > MAX_CSV_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="CSV file too large (max 5 MB)")
    try:
        raw = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(raw))
    rows: list[HistoricalDeliverySeedRow] = []
    for row_num, line in enumerate(reader, start=2):
        if not line.get("delivery_date") or not line.get("metres"):
            continue
        try:
            rate_paise = int(
                (Decimal(line["rate_rs_per_m"].strip()) * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            rows.append(
                HistoricalDeliverySeedRow(
                    delivery_date=date.fromisoformat(line["delivery_date"].strip()),
                    trader_name=line["trader_name"].strip(),
                    challan_no=line["challan_no"].strip(),
                    sort_name=(line.get("sort_name") or "").strip() or None,
                    metres=Decimal(line["metres"].strip()),
                    applied_rate_paise=rate_paise,
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid Deliveries CSV row {row_num}: {exc}",
            ) from exc
    settings = db.scalar(select(UnitSettings).limit(1))
    plan = (
        db.scalar(
            select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).where(
                EbTariffPlan.id == settings.active_tariff_plan_id
            )
        )
        if settings and settings.active_tariff_plan_id
        else None
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active EB tariff plan configured")

    import_historical_seed(db, owner_id=owner.id, tariff_plan=plan, eb_bills=[], deliveries=rows)
    db.commit()
    return {"imported_deliveries": len(rows)}


@router.get("/backup/sqlite")
def download_sqlite_backup(
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Create a transactionally consistent hot SQLite backup (safe across WAL mode)."""
    bind = db.get_bind()
    db_file = None
    if bind.url.database and bind.url.database != ":memory:":
        db_file = Path(bind.url.database)
    else:
        db_file = get_settings().db_path

    if not db_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SQLite database file not found")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    cfg = get_settings()
    scrub_private = not cfg.is_ai_allowed_user(owner) and bool(cfg.ai_allowed_username_set())

    try:
        src_conn = sqlite3.connect(str(db_file))
        dst_conn = sqlite3.connect(str(tmp_path))
        try:
            src_conn.backup(dst_conn)
            if scrub_private:
                priv_names = sorted(cfg.ai_allowed_username_set())
                placeholders = ",".join("?" for _ in priv_names)
                cur = dst_conn.cursor()
                tables = [
                    r[0]
                    for r in cur.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
                cur.execute("PRAGMA foreign_keys=OFF")
                # Always strip private AI Copilot chat history from non-AI backups
                scrubbed_any = False
                for chat_tbl in ("ai_chat_messages", "ai_chat_threads"):
                    if chat_tbl in tables:
                        cur.execute(f'DELETE FROM "{chat_tbl}"')
                        scrubbed_any = True

                priv_ids = [
                    r[0]
                    for r in cur.execute(
                        f"SELECT id FROM users WHERE lower(username) IN ({placeholders})", priv_names
                    ).fetchall()
                ]
                if priv_ids:
                    id_ph = ",".join("?" for _ in priv_ids)
                    # Nullify audit/created_by references before removing private users from the backup copy
                    for tbl in tables:
                        cols = {c[1] for c in cur.execute(f'PRAGMA table_info("{tbl}")').fetchall()}
                        for col in ("created_by", "deleted_by", "changed_by"):
                            if col in cols:
                                cur.execute(f'UPDATE "{tbl}" SET "{col}" = NULL WHERE "{col}" IN ({id_ph})', priv_ids)
                    cur.execute(f"DELETE FROM audit_logs WHERE entity_type='user' AND entity_id IN ({id_ph})", priv_ids)
                    cur.execute(
                        "UPDATE audit_logs SET reason='Owner update' WHERE reason LIKE '%AI Copilot%'"
                    )
                    cur.execute(f"DELETE FROM users WHERE id IN ({id_ph})", priv_ids)
                    scrubbed_any = True

                if scrubbed_any:
                    dst_conn.commit()
                    # VACUUM rewrites all SQLite pages so scrubbed usernames/chats cannot be recovered from free pages
                    dst_conn.execute("VACUUM")
        finally:
            dst_conn.close()
            src_conn.close()
        raw_bytes = tmp_path.read_bytes()
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    record_audit(
        db,
        entity_type="system_backup",
        entity_id=0,
        action="CREATE",
        changed_by=owner.id,
        new_values={"size_bytes": len(raw_bytes)},
        reason="Manual SQLite backup download",
    )
    db.commit()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Response(
        content=raw_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="loomos_backup_{stamp}.db"'},
    )
