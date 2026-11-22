"""Private Multimodal Bilingual LOOMOS AI Copilot powered by Google Gemini (google-genai)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit, snapshot_fields
from app.core.config import get_settings, today_ist
from app.models.core import (
    Advance,
    Alert,
    Beam,
    BeamLoading,
    DefectPrediction,
    Delivery,
    DeliveryItem,
    EbBill,
    EbTariffPlan,
    Expense,
    FabricSort,
    Inspection,
    Loom,
    ShedCalendar,
    ShiftEntry,
    Trader,
    TraderPayment,
    UnitSettings,
    User,
    Weaver,
)
from app.services.analytics_service import (
    calculate_custom_eb_bill,
    compute_beam_etas,
    compute_eb_prediction_and_outage_loss,
    compute_eb_vs_metres_efficiency,
    compute_production_anomalies,
    compute_weekly_forecast,
    estimate_eb_for_metres,
)
from app.services.beam_service import compute_beams_response_list, sync_weft_wastage_alert
from app.services.dashboard_service import compute_floor_dashboard, compute_owner_financials
from app.services.eb_calculator import calculate_bill_breakdown_paise
from app.services.payroll_service import calculate_payroll_preview

ACTION_TOKEN_TTL_SECONDS = 900  # 15 minutes
MAX_TOOL_ROUNDS = 6


def _json_safe(value: Any) -> Any:
    """Recursively convert Decimal / date / datetime / ORM models to clean JSON types."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "__table__"):
        return {col.name: _json_safe(getattr(value, col.name)) for col in value.__table__.columns}
    return value


def _paise_to_rs(paise: int | None) -> float:
    return round(int(paise or 0) / 100.0, 2)


def _rs_to_paise(rupees: float | int | str) -> int:
    try:
        dec = Decimal(str(rupees))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid rupee amount: {rupees}") from exc
    if dec < 0:
        raise ValueError("Rupee amount cannot be negative")
    return int((dec * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_iso_date(val: str | None, *, default_today: bool = True) -> date:
    if not val or not str(val).strip():
        if default_today:
            return today_ist()
        raise ValueError("Date is required (YYYY-MM-DD)")
    raw = str(val).strip()
    if raw.lower() in {"today", "tdy"}:
        return today_ist()
    if raw.lower() in {"yesterday", "yst", "yday"}:
        return today_ist() - timedelta(days=1)
    if raw.lower() in {"tomorrow", "tmrw", "tmr"}:
        return today_ist() + timedelta(days=1)
    # Accept YYYY-MM-DD or DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{2})[/-](\d{2})[/-](\d{4})$", raw)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return date.fromisoformat(raw[:10])


# ---------------------------------------------------------------------------
# HMAC-Signed Pending Action Tokens (Two-Step Confirm / Cancel Safety)
# ---------------------------------------------------------------------------
def create_action_token(
    *,
    user_id: int,
    action_type: str,
    title: str,
    summary: str,
    details: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a tamper-proof signed pending action card for user confirmation."""
    cfg = get_settings()
    body = {
        "uid": user_id,
        "exp": int(time.time()) + ACTION_TOKEN_TTL_SECONDS,
        "nonce": uuid.uuid4().hex[:10],
        "action_type": action_type,
        "title": title,
        "summary": summary,
        "details": details,
        "payload": _json_safe(payload),
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii")
    sig = hmac.new(
        cfg.resolved_secret_key().encode("utf-8"),
        b"loomos_ai_action:" + b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "action_token": f"{b64}.{sig}",
        "action_type": action_type,
        "title": title,
        "summary": summary,
        "details": details,
    }


def verify_action_token(action_token: str, user_id: int) -> dict[str, Any]:
    """Verify HMAC signature, owner binding, and expiry of a pending action token."""
    if not action_token or "." not in action_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action token")
    b64, sig = action_token.rsplit(".", 1)
    cfg = get_settings()
    expected = hmac.new(
        cfg.resolved_secret_key().encode("utf-8"),
        b"loomos_ai_action:" + b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or tampered action token")
    try:
        body = json.loads(base64.urlsafe_b64decode(b64.encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed action token") from exc
    if int(body.get("uid", -1)) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action token belongs to another user")
    if int(body.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action preview expired. Please ask Copilot again.")
    return body


# ---------------------------------------------------------------------------
# Fuzzy Entity Resolvers (handles informal/shortened names cleanly)
# ---------------------------------------------------------------------------
def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _resolve_loom(db: Session, query: str) -> tuple[Loom | None, list[str]]:
    looms = db.scalars(select(Loom).order_by(Loom.loom_number)).all()
    q_raw = (query or "").strip().lower()
    q_norm = _norm(query)
    if not q_norm:
        return None, [l.loom_number for l in looms]
    # 1. Exact case-insensitive match
    for l in looms:
        if l.loom_number.lower() == q_raw or _norm(l.loom_number) == q_norm:
            return l, []
    # 2. Numeric match (e.g. "3" or "L3" or "loom 3" -> "L-03" or "S-03")
    m_num = re.search(r"(\d+)$", q_norm)
    if m_num:
        target_int = int(m_num.group(1))
        prefix_letters = re.sub(r"^(loom|lno)", "", q_norm[: m_num.start()])
        matches = []
        for l in looms:
            lm = re.search(r"(\d+)$", _norm(l.loom_number))
            if lm and int(lm.group(1)) == target_int:
                l_prefix = _norm(l.loom_number)[: lm.start()]
                if not prefix_letters or l_prefix.startswith(prefix_letters) or prefix_letters == "l":
                    matches.append(l)
        if len(matches) == 1:
            return matches[0], []
        if len(matches) > 1:
            return None, [l.loom_number for l in matches]
    # 3. Substring fallback
    sub = [l for l in looms if q_norm in _norm(l.loom_number)]
    if len(sub) == 1:
        return sub[0], []
    return None, [l.loom_number for l in (sub or looms[:12])]


def _resolve_weaver(db: Session, query: str) -> tuple[Weaver | None, list[str]]:
    weavers = db.scalars(select(Weaver).where(Weaver.is_active.is_(True)).order_by(Weaver.full_name)).all()
    q_raw = (query or "").strip().lower()
    q_norm = _norm(query)
    if not q_norm:
        return None, [w.full_name for w in weavers]
    for w in weavers:
        if w.full_name.lower() == q_raw or _norm(w.full_name) == q_norm:
            return w, []
        if w.full_name_ta and w.full_name_ta.strip() == (query or "").strip():
            return w, []
    pref = [w for w in weavers if w.full_name.lower().startswith(q_raw) or _norm(w.full_name).startswith(q_norm)]
    if len(pref) == 1:
        return pref[0], []
    sub = [w for w in weavers if q_raw in w.full_name.lower() or q_norm in _norm(w.full_name)]
    if len(sub) == 1:
        return sub[0], []
    return None, [w.full_name for w in (sub or weavers)]


def _resolve_trader(db: Session, query: str) -> tuple[Trader | None, list[str]]:
    traders = db.scalars(select(Trader).where(Trader.is_active.is_(True)).order_by(Trader.company_name)).all()
    q_raw = (query or "").strip().lower()
    q_norm = _norm(query)
    if not q_norm:
        return None, [t.company_name for t in traders]
    for t in traders:
        if t.company_name.lower() == q_raw or _norm(t.company_name) == q_norm:
            return t, []
    sub = [t for t in traders if q_raw in t.company_name.lower() or q_norm in _norm(t.company_name)]
    if len(sub) == 1:
        return sub[0], []
    return None, [t.company_name for t in (sub or traders)]


def _resolve_sort(db: Session, query: str) -> tuple[FabricSort | None, list[str]]:
    sorts = db.scalars(select(FabricSort).where(FabricSort.is_active.is_(True)).order_by(FabricSort.sort_name)).all()
    q_raw = (query or "").strip().lower()
    q_norm = _norm(query)
    if not q_norm:
        return None, [s.sort_name for s in sorts]
    for s in sorts:
        if s.sort_name.lower() == q_raw or _norm(s.sort_name) == q_norm:
            return s, []
    sub = [s for s in sorts if q_raw in s.sort_name.lower() or q_norm in _norm(s.sort_name)]
    if len(sub) == 1:
        return sub[0], []
    return None, [s.sort_name for s in (sub or sorts)]


# ---------------------------------------------------------------------------
# Live Read Tool Implementations
# ---------------------------------------------------------------------------
def _tool_get_shed_summary(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    days = max(1, min(365, int(args.get("days") or 30)))
    end_d = today_ist()
    start_d = end_d - timedelta(days=days - 1)
    unit = db.scalar(select(UnitSettings).limit(1))
    floor = compute_floor_dashboard(db, period_start=start_d, period_end=end_d, include_financial_alerts=True)
    fin = compute_owner_financials(db, period_start=start_d, period_end=end_d)
    return _json_safe(
        {
            "unit": {
                "unit_name": unit.unit_name if unit else "LOOMOS",
                "location": unit.location if unit else "",
                "shifts_per_day": unit.shifts_per_day if unit else 2,
                "planned_shift_mins": unit.planned_shift_mins if unit else 600,
                "sanctioned_kw": float(unit.sanctioned_kw) if unit else 10.0,
            },
            "period": {"start": start_d, "end": end_d, "days": days, "today_ist": end_d},
            "production": {
                "today_metres": floor["today_metres"],
                "period_metres": floor["period_metres"],
                "active_looms_in_period": floor["active_looms_count"],
                "operational_looms": floor["operational_looms_count"],
                "running_beams": floor["running_beams_count"],
                "availability_pct": floor["availability_pct"],
                "performance_pct": floor["performance_pct"],
                "utilization_ap_pct": floor["utilization_ap_pct"],
                "full_oee_pct": floor["full_oee_pct"],
                "power_cut_mins": floor["total_power_cut_mins"],
                "downtime_mins": floor["total_downtime_mins"],
                "confirmed_defective_metres": floor["confirmed_defective_metres"],
            },
            "financials_rupees": {
                "billed_revenue_rs": _paise_to_rs(fin["billed_revenue_paise"]),
                "finalized_wages_rs": _paise_to_rs(fin["finalized_wages_paise"]),
                "eb_bills_rs": _paise_to_rs(fin["eb_bills_paise"]),
                "expenses_rs": _paise_to_rs(fin["expenses_paise"]),
                "net_operating_rs": _paise_to_rs(fin["net_operating_paise"]),
                "total_receivable_rs": _paise_to_rs(fin["total_receivable_paise"]),
                "total_rate_underpayment_rs": _paise_to_rs(fin["total_rate_underpayment_paise"]),
            },
            "open_alerts_count": len(floor["open_alerts"]),
            "open_alerts": [
                {"id": a.id, "type": a.alert_type, "severity": a.severity, "message": a.message}
                for a in floor["open_alerts"][:10]
            ],
            "loom_breakdown": floor["loom_breakdown"],
        }
    )


def _tool_list_looms(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    include_inactive = bool(args.get("include_inactive", False))
    stmt = select(Loom).order_by(Loom.loom_number)
    if not include_inactive:
        stmt = stmt.where(Loom.is_active.is_(True))
    looms = db.scalars(stmt).all()
    beams = {b["id"]: b for b in compute_beams_response_list(db)}
    active_loadings = {
        bl.loom_id: bl.beam_id
        for bl in db.scalars(select(BeamLoading).where(BeamLoading.unloaded_at.is_(None))).all()
    }
    rows = []
    for l in looms:
        b_id = active_loadings.get(l.id)
        b = beams.get(b_id) if b_id else None
        rows.append(
            {
                "id": l.id,
                "loom_number": l.loom_number,
                "loom_type": l.loom_type,
                "make_model": l.make_model,
                "rated_rpm": l.rated_rpm,
                "reed_space_in": l.reed_space_in,
                "status": l.status,
                "is_active": l.is_active,
                "active_beam_no": b["beam_no"] if b else None,
                "active_sort": b["sort_name"] if b else None,
                "remaining_beam_m": b["remaining_m"] if b else None,
            }
        )
    return _json_safe({"count": len(rows), "looms": rows})


def _tool_list_beams_and_etas(db: Session, _args: dict[str, Any]) -> dict[str, Any]:
    beams = compute_beams_response_list(db)
    etas = compute_beam_etas(db)
    return _json_safe({"beams": beams[:40], "running_etas": etas})


def _tool_list_weavers_and_payroll(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    days = max(1, min(90, int(args.get("days") or 7)))
    end_d = today_ist()
    start_d = end_d - timedelta(days=days - 1)
    weavers = db.scalars(
        select(Weaver).options(selectinload(Weaver.wage_rules)).where(Weaver.is_active.is_(True)).order_by(Weaver.full_name)
    ).all()
    preview = calculate_payroll_preview(db, period_start=start_d, period_end=end_d)
    recent_advs = db.scalars(
        select(Advance)
        .where(Advance.is_deleted.is_(False), Advance.advance_date >= end_d - timedelta(days=30))
        .order_by(Advance.advance_date.desc())
        .limit(20)
    ).all()
    w_names = {w.id: w.full_name for w in weavers}
    return _json_safe(
        {
            "period": {"start": start_d, "end": end_d},
            "weavers": [
                {
                    "id": w.id,
                    "full_name": w.full_name,
                    "role_type": w.role_type,
                    "phone": w.phone,
                    "active_wage_rules": [
                        {
                            "wage_mode": r.wage_mode,
                            "rate_rs": _paise_to_rs(r.rate_paise),
                            "effective_from": r.effective_from,
                        }
                        for r in w.wage_rules
                        if not r.is_deleted and r.effective_to is None
                    ],
                }
                for w in weavers
            ],
            "payroll_preview": [
                {
                    "weaver_name": p["weaver_name"],
                    "role_type": p["role_type"],
                    "wage_mode": p["wage_mode"],
                    "units_worked": p["units_worked"],
                    "rate_rs": _paise_to_rs(p["rate_paise"]),
                    "gross_rs": _paise_to_rs(p["gross_paise"]),
                    "advance_deducted_rs": _paise_to_rs(p["advance_deducted_paise"]),
                    "net_payable_rs": _paise_to_rs(p["net_payable_paise"]),
                }
                for p in preview
            ],
            "recent_advances_30d": [
                {
                    "id": a.id,
                    "weaver_name": w_names.get(a.weaver_id, f"Weaver #{a.weaver_id}"),
                    "date": a.advance_date,
                    "amount_rs": _paise_to_rs(a.amount_paise),
                    "note": a.note,
                }
                for a in recent_advs
            ],
        }
    )


def _tool_list_traders_and_sorts(db: Session, _args: dict[str, Any]) -> dict[str, Any]:
    traders = db.scalars(select(Trader).where(Trader.is_active.is_(True)).order_by(Trader.company_name)).all()
    sorts = db.scalars(select(FabricSort).where(FabricSort.is_active.is_(True)).order_by(FabricSort.sort_name)).all()
    deliveries = db.scalars(select(Delivery).where(Delivery.is_deleted.is_(False))).all()
    del_map = {d.id: d for d in deliveries}
    items = db.scalars(select(DeliveryItem).where(DeliveryItem.is_deleted.is_(False))).all()
    payments = db.scalars(select(TraderPayment).where(TraderPayment.is_deleted.is_(False))).all()
    sort_map = {s.id: s for s in sorts}

    billed_by_t: dict[int, int] = {}
    under_by_t: dict[int, int] = {}
    metres_by_t: dict[int, Decimal] = {}
    for it in items:
        d = del_map.get(it.delivery_id)
        if not d:
            continue
        amt = int((it.metres * Decimal(it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        billed_by_t[d.trader_id] = billed_by_t.get(d.trader_id, 0) + amt
        metres_by_t[d.trader_id] = metres_by_t.get(d.trader_id, Decimal("0")) + it.metres
        srt = sort_map.get(it.sort_id) if it.sort_id else None
        if srt and it.applied_rate_paise < srt.agreed_rate_paise:
            short = int((it.metres * Decimal(srt.agreed_rate_paise - it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            under_by_t[d.trader_id] = under_by_t.get(d.trader_id, 0) + short

    rec_by_t: dict[int, int] = {}
    for p in payments:
        rec_by_t[p.trader_id] = rec_by_t.get(p.trader_id, 0) + p.amount_paise + p.shortage_deduction_paise

    return _json_safe(
        {
            "traders": [
                {
                    "id": t.id,
                    "company_name": t.company_name,
                    "contact_name": t.contact_name,
                    "phone": t.phone,
                    "total_metres": metres_by_t.get(t.id, Decimal("0")),
                    "billed_rs": _paise_to_rs(billed_by_t.get(t.id, 0)),
                    "received_rs": _paise_to_rs(rec_by_t.get(t.id, 0)),
                    "balance_receivable_rs": _paise_to_rs(billed_by_t.get(t.id, 0) - rec_by_t.get(t.id, 0)),
                    "rate_underpayment_rs": _paise_to_rs(under_by_t.get(t.id, 0)),
                }
                for t in traders
            ],
            "fabric_sorts": [
                {
                    "id": s.id,
                    "sort_name": s.sort_name,
                    "warp_count": s.warp_count,
                    "weft_count": s.weft_count,
                    "reed": s.reed,
                    "pick": s.pick,
                    "width_in": s.width_in,
                    "agreed_rate_rs": _paise_to_rs(s.agreed_rate_paise),
                    "expected_weft_kg_per_100m": s.expected_weft_kg_per_100m,
                    "wastage_pct": s.wastage_pct,
                }
                for s in sorts
            ],
        }
    )


def _tool_get_eb_overview(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    pred = compute_eb_prediction_and_outage_loss(db)
    eff = compute_eb_vs_metres_efficiency(db)
    bills = db.scalars(select(EbBill).where(EbBill.is_deleted.is_(False)).order_by(EbBill.period_end.desc()).limit(10)).all()
    out: dict[str, Any] = {
        "prediction": {
            "tariff_name": pred["tariff_name"],
            "sanctioned_kw": pred["sanctioned_kw"],
            "projected_units_kwh": pred["projected_units_kwh"],
            "projected_net_bill_rs": _paise_to_rs(pred["projected_net_bill_paise"]),
            "slab_note": pred["slab_note"],
            "outage_30d_stopped_hrs": pred["outage_30d_stopped_hrs"],
            "outage_30d_lost_metres": pred["outage_30d_lost_metres"],
            "outage_30d_lost_revenue_rs": _paise_to_rs(pred["outage_30d_lost_revenue_paise"]),
        },
        "efficiency": {
            "avg_kwh_per_metre": eff["avg_kwh_per_metre"],
            "avg_metres_per_kwh": eff["avg_metres_per_kwh"],
            "avg_eb_rs_per_metre": _paise_to_rs(eff["avg_eb_paise_per_metre"]) if eff["avg_eb_paise_per_metre"] is not None else None,
            "model_kind": eff["model_kind"],
            "recent_cycles": eff["periods"][:8],
        },
        "recent_bills": [
            {
                "id": b.id,
                "period_start": b.period_start,
                "period_end": b.period_end,
                "units_kwh": b.units_consumed,
                "net_bill_rs": _paise_to_rs(b.net_bill_paise),
                "power_cut_mins": b.total_power_cut_mins,
                "notes": b.notes,
            }
            for b in bills
        ],
    }
    if args.get("estimate_metres") is not None:
        est = estimate_eb_for_metres(db, float(args["estimate_metres"]))
        out["estimate_for_metres"] = {
            **est,
            "estimated_bill_rs": _paise_to_rs(est["estimated_bill_paise"]),
            "eb_rs_per_metre": _paise_to_rs(est["eb_paise_per_metre"]),
        }
    if args.get("calc_units_kwh") is not None:
        calc = calculate_custom_eb_bill(db, units_kwh=float(args["calc_units_kwh"]))
        out["custom_eb_calculation"] = {
            **calc,
            "net_bill_rs": _paise_to_rs(calc["net_bill_paise"]),
            "energy_rs": _paise_to_rs(calc["energy_paise"]),
            "fixed_rs": _paise_to_rs(calc["fixed_paise"]),
            "tax_rs": _paise_to_rs(calc["tax_paise"]),
        }
    return _json_safe(out)


def _tool_get_recent_shifts_and_anomalies(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    days = max(1, min(60, int(args.get("days") or 7)))
    end_d = today_ist()
    start_d = end_d - timedelta(days=days - 1)
    stmt = (
        select(ShiftEntry)
        .where(ShiftEntry.is_deleted.is_(False), ShiftEntry.entry_date >= start_d, ShiftEntry.entry_date <= end_d)
        .order_by(ShiftEntry.entry_date.desc(), ShiftEntry.shift_no.desc(), ShiftEntry.loom_id)
    )
    loom_filter = args.get("loom_number")
    if loom_filter:
        loom_obj, cands = _resolve_loom(db, str(loom_filter))
        if not loom_obj:
            return {"error": f"Loom '{loom_filter}' not found.", "available_looms": cands}
        stmt = stmt.where(ShiftEntry.loom_id == loom_obj.id)

    rows = db.scalars(stmt.limit(80)).all()
    looms = {l.id: l.loom_number for l in db.scalars(select(Loom)).all()}
    weavers = {w.id: w.full_name for w in db.scalars(select(Weaver)).all()}
    anomalies = compute_production_anomalies(db)
    return _json_safe(
        {
            "period": {"start": start_d, "end": end_d},
            "total_metres_in_rows": round(sum(float(r.net_metres) for r in rows), 2),
            "shifts": [
                {
                    "id": r.id,
                    "date": r.entry_date,
                    "shift_no": r.shift_no,
                    "loom_number": looms.get(r.loom_id, f"#{r.loom_id}"),
                    "weaver_name": weavers.get(r.weaver_id, f"#{r.weaver_id}"),
                    "net_metres": r.net_metres,
                    "power_cut_mins": r.power_cut_mins,
                    "downtime_mins": r.downtime_mins,
                    "defective_metres": r.defective_metres,
                    "notes": r.notes,
                }
                for r in rows
            ],
            "anomalies": anomalies[:10],
        }
    )


def _tool_get_recent_deliveries_and_expenses(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    limit = max(1, min(30, int(args.get("limit") or 12)))
    traders = {t.id: t.company_name for t in db.scalars(select(Trader)).all()}
    sorts = {s.id: s for s in db.scalars(select(FabricSort)).all()}
    deliveries = db.scalars(
        select(Delivery).where(Delivery.is_deleted.is_(False)).order_by(Delivery.delivery_date.desc(), Delivery.id.desc()).limit(limit)
    ).all()
    del_ids = [d.id for d in deliveries]
    items = db.scalars(select(DeliveryItem).where(DeliveryItem.delivery_id.in_(del_ids), DeliveryItem.is_deleted.is_(False))).all() if del_ids else []
    by_del: dict[int, list[DeliveryItem]] = {}
    for it in items:
        by_del.setdefault(it.delivery_id, []).append(it)

    del_rows = []
    for d in deliveries:
        tot_p = 0
        under_p = 0
        line_summaries = []
        for it in by_del.get(d.id, []):
            srt = sorts.get(it.sort_id) if it.sort_id else None
            amt = int((it.metres * Decimal(it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            tot_p += amt
            if srt and it.applied_rate_paise < srt.agreed_rate_paise:
                under_p += int((it.metres * Decimal(srt.agreed_rate_paise - it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            line_summaries.append(
                {
                    "sort": srt.sort_name if srt else None,
                    "metres": it.metres,
                    "applied_rate_rs": _paise_to_rs(it.applied_rate_paise),
                    "agreed_rate_rs": _paise_to_rs(srt.agreed_rate_paise) if srt else None,
                }
            )
        del_rows.append(
            {
                "id": d.id,
                "date": d.delivery_date,
                "challan_no": d.challan_no,
                "trader": traders.get(d.trader_id, f"#{d.trader_id}"),
                "total_metres": d.total_metres,
                "total_rs": _paise_to_rs(tot_p),
                "rate_cut_shortfall_rs": _paise_to_rs(under_p),
                "items": line_summaries,
            }
        )

    expenses = db.scalars(
        select(Expense).where(Expense.is_deleted.is_(False)).order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(limit)
    ).all()
    payments = db.scalars(
        select(TraderPayment).where(TraderPayment.is_deleted.is_(False)).order_by(TraderPayment.payment_date.desc(), TraderPayment.id.desc()).limit(limit)
    ).all()

    return _json_safe(
        {
            "deliveries": del_rows,
            "payments": [
                {
                    "id": p.id,
                    "date": p.payment_date,
                    "trader": traders.get(p.trader_id, f"#{p.trader_id}"),
                    "amount_rs": _paise_to_rs(p.amount_paise),
                    "shortage_deduction_rs": _paise_to_rs(p.shortage_deduction_paise),
                    "reference": p.reference,
                }
                for p in payments
            ],
            "expenses": [
                {
                    "id": e.id,
                    "date": e.expense_date,
                    "category": e.category,
                    "amount_rs": _paise_to_rs(e.amount_paise),
                    "note": e.note,
                }
                for e in expenses
            ],
        }
    )


def _tool_get_forecast_and_alerts(db: Session, _args: dict[str, Any]) -> dict[str, Any]:
    fc = compute_weekly_forecast(db)
    alerts = db.scalars(
        select(Alert).where(Alert.status == "OPEN").order_by(Alert.created_at.desc(), Alert.id.desc()).limit(25)
    ).all()
    return _json_safe(
        {
            "forecast": fc,
            "open_alerts": [
                {"id": a.id, "type": a.alert_type, "severity": a.severity, "message": a.message, "created_at": a.created_at}
                for a in alerts
            ],
        }
    )


def _tool_get_recent_inspections(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    limit = max(1, min(20, int(args.get("limit") or 10)))
    insps = db.scalars(select(Inspection).order_by(Inspection.id.desc()).limit(limit)).all()
    looms = {l.id: l.loom_number for l in db.scalars(select(Loom)).all()}
    out = []
    for ins in insps:
        pred = db.scalar(
            select(DefectPrediction).where(DefectPrediction.inspection_id == ins.id).order_by(DefectPrediction.id.desc()).limit(1)
        )
        out.append(
            {
                "id": ins.id,
                "inspected_at": ins.inspected_at,
                "loom_number": looms.get(ins.loom_id) if ins.loom_id else None,
                "review_status": ins.review_status,
                "reviewed_label": ins.reviewed_label,
                "defective_metres": ins.defective_metres,
                "predicted_label": pred.predicted_label if pred else None,
                "confidence": float(pred.confidence) if pred else None,
            }
        )
    return _json_safe({"inspections": out})


# ---------------------------------------------------------------------------
# Safe Write Action Proposal Builders (return preview + signed token)
# ---------------------------------------------------------------------------
def _propose_action(
    db: Session,
    owner: User,
    tool_name: str,
    args: dict[str, Any],
    pending_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        if tool_name == "propose_add_looms":
            count = max(1, min(100, int(args.get("count") or 1)))
            prefix = str(args.get("prefix") or "L-").strip() or "L-"
            loom_type = str(args.get("loom_type") or "SHUTTLE").upper()
            if loom_type not in {"SHUTTLE", "RAPIER", "AIRJET", "WATERJET", "PROJECTILE"}:
                return {"error": f"Invalid loom_type '{loom_type}'. Choose SHUTTLE, RAPIER, AIRJET, WATERJET, or PROJECTILE."}
            rated_rpm = max(40, min(2500, int(args.get("rated_rpm") or 160)))
            reed_space_in = max(20, min(220, int(args.get("reed_space_in") or 56)))
            make_model = str(args.get("make_model") or "").strip()[:80]
            existing_nums = set(db.scalars(select(Loom.loom_number)).all())
            start_num = args.get("start_number")
            if start_num is None:
                max_n = 0
                for num in existing_nums:
                    if num.startswith(prefix):
                        m = re.search(r"(\d+)$", num)
                        if m:
                            max_n = max(max_n, int(m.group(1)))
                start_num = max_n + 1
            else:
                start_num = max(1, int(start_num))
            planned = [f"{prefix}{start_num + i:02d}" for i in range(count)]
            conflicts = [n for n in planned if n in existing_nums]
            if conflicts:
                return {"error": f"Loom numbers already exist: {', '.join(conflicts)}. Specify a different prefix or start_number."}
            card = create_action_token(
                user_id=owner.id,
                action_type="add_looms",
                title=f"Add {count} {loom_type.title()} Loom{'s' if count > 1 else ''}",
                summary=f"Create {', '.join(planned[:5])}{'...' if len(planned) > 5 else ''} ({rated_rpm} RPM, {reed_space_in}\" reed)",
                details=[
                    f"Loom Numbers: {', '.join(planned)}",
                    f"Type: {loom_type} · RPM: {rated_rpm} · Reed: {reed_space_in}\"",
                    *( [f"Make/Model: {make_model}"] if make_model else [] ),
                ],
                payload={
                    "count": count,
                    "prefix": prefix,
                    "start_number": start_num,
                    "loom_type": loom_type,
                    "make_model": make_model,
                    "rated_rpm": rated_rpm,
                    "reed_space_in": reed_space_in,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_update_loom":
            loom_obj, cands = _resolve_loom(db, str(args.get("loom_number") or ""))
            if not loom_obj:
                return {"error": f"Could not match loom '{args.get('loom_number')}'.", "available_looms": cands}
            updates: dict[str, Any] = {}
            details = [f"Loom: {loom_obj.loom_number}"]
            if args.get("status"):
                st = str(args["status"]).upper()
                if st not in {"OPERATIONAL", "UNDER_MAINTENANCE", "IDLE"}:
                    return {"error": "status must be OPERATIONAL, UNDER_MAINTENANCE, or IDLE"}
                updates["status"] = st
                details.append(f"Status: {loom_obj.status} -> {st}")
            if args.get("rated_rpm") is not None:
                rpm = max(40, min(2500, int(args["rated_rpm"])))
                updates["rated_rpm"] = rpm
                details.append(f"Rated RPM: {loom_obj.rated_rpm} -> {rpm}")
            if args.get("make_model") is not None:
                updates["make_model"] = str(args["make_model"]).strip()[:80]
                details.append(f"Make/Model: {updates['make_model']}")
            if args.get("is_active") is not None:
                updates["is_active"] = bool(args["is_active"])
                details.append(f"Active: {loom_obj.is_active} -> {updates['is_active']}")
            if not updates:
                return {"error": "No changes specified for the loom."}
            card = create_action_token(
                user_id=owner.id,
                action_type="update_loom",
                title=f"Update Loom {loom_obj.loom_number}",
                summary=f"Update {loom_obj.loom_number}: " + ", ".join(f"{k}={v}" for k, v in updates.items()),
                details=details,
                payload={"loom_id": loom_obj.id, "loom_number": loom_obj.loom_number, "updates": updates},
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_record_advance":
            weaver, cands = _resolve_weaver(db, str(args.get("weaver_name") or ""))
            if not weaver:
                return {"error": f"Could not uniquely match weaver '{args.get('weaver_name')}'.", "candidates": cands}
            amt_p = _rs_to_paise(args["amount_rupees"])
            if amt_p <= 0:
                return {"error": "Advance amount must be greater than ₹0."}
            adv_date = _parse_iso_date(args.get("advance_date"), default_today=True)
            note = str(args.get("note") or "").strip()[:255] or None
            card = create_action_token(
                user_id=owner.id,
                action_type="record_advance",
                title="Record Weaver Advance (Uthaav)",
                summary=f"₹{amt_p / 100:,.2f} advance to {weaver.full_name} on {adv_date.strftime('%d/%m/%Y')}",
                details=[
                    f"Worker: {weaver.full_name} ({weaver.role_type})",
                    f"Amount: ₹{amt_p / 100:,.2f}",
                    f"Date: {adv_date.strftime('%d/%m/%Y')}",
                    *( [f"Note: {note}"] if note else [] ),
                ],
                payload={
                    "weaver_id": weaver.id,
                    "weaver_name": weaver.full_name,
                    "amount_paise": amt_p,
                    "advance_date": adv_date.isoformat(),
                    "note": note,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_record_expense":
            category = str(args.get("category") or "General").strip()[:60]
            amt_p = _rs_to_paise(args["amount_rupees"])
            if amt_p <= 0:
                return {"error": "Expense amount must be greater than ₹0."}
            exp_date = _parse_iso_date(args.get("expense_date"), default_today=True)
            note = str(args.get("note") or "").strip()[:255] or None
            card = create_action_token(
                user_id=owner.id,
                action_type="record_expense",
                title="Record Shed Expense",
                summary=f"₹{amt_p / 100:,.2f} ({category}) on {exp_date.strftime('%d/%m/%Y')}",
                details=[
                    f"Category: {category}",
                    f"Amount: ₹{amt_p / 100:,.2f}",
                    f"Date: {exp_date.strftime('%d/%m/%Y')}",
                    *( [f"Note: {note}"] if note else [] ),
                ],
                payload={
                    "category": category,
                    "amount_paise": amt_p,
                    "expense_date": exp_date.isoformat(),
                    "note": note,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_record_trader_payment":
            trader, cands = _resolve_trader(db, str(args.get("trader_name") or ""))
            if not trader:
                return {"error": f"Could not uniquely match trader '{args.get('trader_name')}'.", "candidates": cands}
            amt_p = _rs_to_paise(args["amount_rupees"])
            short_p = _rs_to_paise(args.get("shortage_deduction_rupees") or 0)
            pay_date = _parse_iso_date(args.get("payment_date"), default_today=True)
            ref = str(args.get("reference") or "").strip()[:120] or None
            card = create_action_token(
                user_id=owner.id,
                action_type="record_trader_payment",
                title="Record Trader Payment",
                summary=f"₹{amt_p / 100:,.2f} received from {trader.company_name} on {pay_date.strftime('%d/%m/%Y')}",
                details=[
                    f"Trader: {trader.company_name}",
                    f"Amount Received: ₹{amt_p / 100:,.2f}",
                    *( [f"Shortage Deduction: ₹{short_p / 100:,.2f}"] if short_p > 0 else [] ),
                    f"Date: {pay_date.strftime('%d/%m/%Y')}",
                    *( [f"Reference: {ref}"] if ref else [] ),
                ],
                payload={
                    "trader_id": trader.id,
                    "trader_name": trader.company_name,
                    "amount_paise": amt_p,
                    "shortage_deduction_paise": short_p,
                    "payment_date": pay_date.isoformat(),
                    "reference": ref,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_create_delivery":
            trader, cands = _resolve_trader(db, str(args.get("trader_name") or ""))
            if not trader:
                return {"error": f"Could not uniquely match trader '{args.get('trader_name')}'.", "candidates": cands}
            challan_no = str(args.get("challan_no") or "").strip()[:60]
            if not challan_no:
                return {"error": "challan_no is required."}
            del_date = _parse_iso_date(args.get("delivery_date"), default_today=True)
            raw_items = args.get("items") or []
            if isinstance(raw_items, str):
                raw_items = json.loads(raw_items)
            if not raw_items:
                return {"error": "At least one delivery line item is required."}
            parsed_items = []
            details = [f"Trader: {trader.company_name}", f"Challan: {challan_no} · Date: {del_date.strftime('%d/%m/%Y')}"]
            total_m = Decimal("0.00")
            total_p = 0
            total_under = 0
            for it in raw_items:
                sort_id = None
                sort_label = "Custom"
                agreed_p = None
                if it.get("sort_name"):
                    srt, s_cands = _resolve_sort(db, str(it["sort_name"]))
                    if not srt:
                        return {"error": f"Could not match fabric sort '{it['sort_name']}'.", "candidates": s_cands}
                    sort_id = srt.id
                    sort_label = srt.sort_name
                    agreed_p = srt.agreed_rate_paise
                metres = Decimal(str(it["metres"])).quantize(Decimal("0.01"))
                if metres <= 0:
                    return {"error": "Item metres must be > 0"}
                rate_p = _rs_to_paise(it["applied_rate_rupees"]) if it.get("applied_rate_rupees") is not None else (agreed_p or 0)
                if rate_p <= 0:
                    return {"error": "applied_rate_rupees must be > 0"}
                pieces = max(1, int(it.get("pieces") or 1))
                amt = int((metres * Decimal(rate_p)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                total_m += metres
                total_p += amt
                warn = ""
                if agreed_p and rate_p < agreed_p:
                    short = int((metres * Decimal(agreed_p - rate_p)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    total_under += short
                    warn = f" [RATE CUT! Agreed ₹{agreed_p/100:.2f}, Shortfall ₹{short/100:.2f}]"
                details.append(f"• {sort_label}: {metres} m ({pieces} pcs) @ ₹{rate_p/100:.2f}/m = ₹{amt/100:,.2f}{warn}")
                parsed_items.append(
                    {
                        "sort_id": sort_id,
                        "pieces": pieces,
                        "metres": str(metres),
                        "applied_rate_paise": rate_p,
                    }
                )
            details.append(f"Total: {total_m} m · ₹{total_p/100:,.2f}")
            card = create_action_token(
                user_id=owner.id,
                action_type="create_delivery",
                title=f"Save Delivery Challan {challan_no}",
                summary=f"{trader.company_name}: {total_m} m = ₹{total_p/100:,.2f}" + (f" (⚠ Rate cut ₹{total_under/100:.2f})" if total_under > 0 else ""),
                details=details,
                payload={
                    "trader_id": trader.id,
                    "challan_no": challan_no,
                    "delivery_date": del_date.isoformat(),
                    "items": parsed_items,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"], "rate_cut_shortfall_rs": _paise_to_rs(total_under)}

        if tool_name == "propose_create_eb_bill":
            p_start = _parse_iso_date(args.get("period_start"), default_today=False)
            p_end = _parse_iso_date(args.get("period_end"), default_today=False)
            if p_end < p_start:
                return {"error": "period_end must be on or after period_start."}
            units = Decimal(str(args["units_consumed"])).quantize(Decimal("0.01"))
            net_p = _rs_to_paise(args["net_bill_rupees"])
            pc_mins = max(0, int(args.get("total_power_cut_mins") or 0))
            notes = str(args.get("notes") or "").strip()[:255] or None
            card = create_action_token(
                user_id=owner.id,
                action_type="create_eb_bill",
                title="Save TNPDCL EB Bill",
                summary=f"{units} kWh · ₹{net_p/100:,.2f} ({p_start.strftime('%d/%m/%Y')} to {p_end.strftime('%d/%m/%Y')})",
                details=[
                    f"Billing Period: {p_start.strftime('%d/%m/%Y')} → {p_end.strftime('%d/%m/%Y')}",
                    f"Units Consumed: {units} kWh",
                    f"Net Bill: ₹{net_p/100:,.2f}",
                    *( [f"Power Cut Logged: {pc_mins} mins"] if pc_mins > 0 else [] ),
                    *( [f"Notes: {notes}"] if notes else [] ),
                ],
                payload={
                    "period_start": p_start.isoformat(),
                    "period_end": p_end.isoformat(),
                    "units_consumed": str(units),
                    "net_bill_paise": net_p,
                    "total_power_cut_mins": pc_mins,
                    "notes": notes,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_update_sort_rate":
            srt, cands = _resolve_sort(db, str(args.get("sort_name") or ""))
            if not srt:
                return {"error": f"Could not uniquely match fabric sort '{args.get('sort_name')}'.", "candidates": cands}
            updates: dict[str, Any] = {}
            details = [f"Fabric Sort: {srt.sort_name}"]
            if args.get("agreed_rate_rupees") is not None:
                rp = _rs_to_paise(args["agreed_rate_rupees"])
                if rp <= 0:
                    return {"error": "Agreed rate must be > ₹0."}
                updates["agreed_rate_paise"] = rp
                details.append(f"Agreed Rate: ₹{srt.agreed_rate_paise/100:.2f}/m -> ₹{rp/100:.2f}/m")
            if args.get("wastage_pct") is not None:
                wp = Decimal(str(args["wastage_pct"])).quantize(Decimal("0.01"))
                updates["wastage_pct"] = str(wp)
                details.append(f"Allowed Wastage: {srt.wastage_pct}% -> {wp}%")
            if args.get("expected_weft_kg_per_100m") is not None:
                ew = Decimal(str(args["expected_weft_kg_per_100m"])).quantize(Decimal("0.001"))
                updates["expected_weft_kg_per_100m"] = str(ew)
                details.append(f"Expected Weft/100m: {srt.expected_weft_kg_per_100m} kg -> {ew} kg")
            if not updates:
                return {"error": "No sort rate or wastage updates provided."}
            card = create_action_token(
                user_id=owner.id,
                action_type="update_sort_rate",
                title=f"Update Sort: {srt.sort_name}",
                summary=f"Update {srt.sort_name} (" + ", ".join(details[1:]) + ")",
                details=details,
                payload={"sort_id": srt.id, "updates": updates},
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_save_shift_entries":
            e_date = _parse_iso_date(args.get("entry_date"), default_today=True)
            shift_no = int(args.get("shift_no") or 1)
            if shift_no not in {1, 2, 3}:
                return {"error": "shift_no must be 1, 2, or 3."}
            raw_entries = args.get("entries") or []
            if isinstance(raw_entries, str):
                raw_entries = json.loads(raw_entries)
            if not raw_entries:
                return {"error": "Provide at least one shift entry row."}
            active_loadings = {
                bl.loom_id: bl.beam_id
                for bl in db.scalars(select(BeamLoading).where(BeamLoading.unloaded_at.is_(None))).all()
            }
            default_weaver = db.scalar(select(Weaver).where(Weaver.is_active.is_(True)).order_by(Weaver.id).limit(1))
            parsed_rows = []
            details = [f"Date: {e_date.strftime('%d/%m/%Y')} · Shift #{shift_no}"]
            for row in raw_entries:
                loom_obj, l_cands = _resolve_loom(db, str(row.get("loom_number") or ""))
                if not loom_obj:
                    return {"error": f"Loom '{row.get('loom_number')}' not found.", "available_looms": l_cands}
                weaver_obj = None
                if row.get("weaver_name"):
                    weaver_obj, w_cands = _resolve_weaver(db, str(row["weaver_name"]))
                    if not weaver_obj:
                        return {"error": f"Weaver '{row.get('weaver_name')}' not found.", "candidates": w_cands}
                else:
                    # Carry forward last weaver on this loom
                    last_sh = db.scalar(
                        select(ShiftEntry)
                        .where(ShiftEntry.loom_id == loom_obj.id, ShiftEntry.is_deleted.is_(False))
                        .order_by(ShiftEntry.entry_date.desc(), ShiftEntry.id.desc())
                        .limit(1)
                    )
                    if last_sh:
                        weaver_obj = db.get(Weaver, last_sh.weaver_id)
                    if not weaver_obj:
                        weaver_obj = default_weaver
                if not weaver_obj:
                    return {"error": "No active weaver exists in LOOMOS yet. Create a weaver first."}
                net_m = Decimal(str(row["net_metres"])).quantize(Decimal("0.01"))
                if net_m < 0:
                    return {"error": "net_metres cannot be negative"}
                pc = max(0, int(row.get("power_cut_mins") or 0))
                dt = max(0, int(row.get("downtime_mins") or 0))
                dm = Decimal(str(row.get("defective_metres") or 0)).quantize(Decimal("0.01"))
                note = str(row.get("notes") or "").strip()[:255] or None
                beam_id = active_loadings.get(loom_obj.id)
                details.append(
                    f"• {loom_obj.loom_number} ({weaver_obj.full_name}): {net_m} m"
                    + (f" · Power cut {pc}m" if pc else "")
                    + (f" · Downtime {dt}m" if dt else "")
                    + (f" · Defect {dm}m" if dm > 0 else "")
                )
                parsed_rows.append(
                    {
                        "loom_id": loom_obj.id,
                        "weaver_id": weaver_obj.id,
                        "beam_id": beam_id,
                        "net_metres": str(net_m),
                        "power_cut_mins": pc,
                        "downtime_mins": dt,
                        "defective_metres": str(dm),
                        "notes": note,
                    }
                )
            tot_m = sum((Decimal(r["net_metres"]) for r in parsed_rows), Decimal("0.00"))
            card = create_action_token(
                user_id=owner.id,
                action_type="save_shift_entries",
                title=f"Save Shift #{shift_no} Production ({len(parsed_rows)} loom{'s' if len(parsed_rows) > 1 else ''})",
                summary=f"{e_date.strftime('%d/%m/%Y')} Shift #{shift_no} · Total {tot_m} m across {len(parsed_rows)} loom(s)",
                details=details,
                payload={"entry_date": e_date.isoformat(), "shift_no": shift_no, "rows": parsed_rows},
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_update_unit_settings":
            unit = db.scalar(select(UnitSettings).limit(1))
            if not unit:
                return {"error": "Unit settings not initialized."}
            updates: dict[str, Any] = {}
            details = []
            if args.get("unit_name"):
                updates["unit_name"] = str(args["unit_name"]).strip()[:120]
                details.append(f"Shed Name: {unit.unit_name} -> {updates['unit_name']}")
            if args.get("location") is not None:
                updates["location"] = str(args["location"]).strip()[:120]
                details.append(f"Location: {unit.location} -> {updates['location']}")
            if args.get("shifts_per_day") is not None:
                sp = int(args["shifts_per_day"])
                if sp not in {1, 2, 3}:
                    return {"error": "shifts_per_day must be 1, 2, or 3"}
                updates["shifts_per_day"] = sp
                details.append(f"Shifts/Day: {unit.shifts_per_day} -> {sp}")
            if args.get("planned_shift_mins") is not None:
                pm = max(60, min(1440, int(args["planned_shift_mins"])))
                updates["planned_shift_mins"] = pm
                details.append(f"Shift Duration: {unit.planned_shift_mins} -> {pm} mins")
            if args.get("sanctioned_kw") is not None:
                kw = Decimal(str(args["sanctioned_kw"])).quantize(Decimal("0.01"))
                if kw <= 0:
                    return {"error": "sanctioned_kw must be > 0"}
                updates["sanctioned_kw"] = str(kw)
                details.append(f"Sanctioned Load: {unit.sanctioned_kw} kW -> {kw} kW")
            if not updates:
                return {"error": "No settings changes provided."}
            card = create_action_token(
                user_id=owner.id,
                action_type="update_unit_settings",
                title="Update Shed Settings",
                summary=", ".join(details),
                details=details,
                payload={"updates": updates},
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_update_alert":
            alert_id = int(args["alert_id"])
            alert = db.get(Alert, alert_id)
            if not alert:
                return {"error": f"Alert #{alert_id} not found."}
            st = str(args.get("status") or "DISMISSED").upper()
            if st not in {"OPEN", "ACKNOWLEDGED", "DISMISSED"}:
                return {"error": "status must be OPEN, ACKNOWLEDGED, or DISMISSED"}
            card = create_action_token(
                user_id=owner.id,
                action_type="update_alert",
                title=f"Mark Alert #{alert_id} as {st}",
                summary=alert.message,
                details=[f"Alert #{alert_id} ({alert.alert_type}): {alert.status} -> {st}", alert.message],
                payload={"alert_id": alert_id, "status": st},
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        if tool_name == "propose_set_calendar_day":
            cal_date = _parse_iso_date(args.get("calendar_date"), default_today=False)
            is_work = bool(args.get("is_working_day", False))
            planned_shifts = 0 if not is_work else max(1, min(3, int(args.get("planned_shifts") or 2)))
            note = str(args.get("note") or "").strip()[:255] or None
            label = f"Working Day ({planned_shifts} shifts)" if is_work else "Holiday / Shed Closed"
            card = create_action_token(
                user_id=owner.id,
                action_type="set_calendar_day",
                title=f"Update Shed Calendar ({cal_date.strftime('%d/%m/%Y')})",
                summary=f"{cal_date.strftime('%d/%m/%Y')}: {label}" + (f" — {note}" if note else ""),
                details=[f"Date: {cal_date.strftime('%d/%m/%Y')}", f"Status: {label}", *( [f"Note: {note}"] if note else [] )],
                payload={
                    "calendar_date": cal_date.isoformat(),
                    "is_working_day": is_work,
                    "planned_shifts": planned_shifts,
                    "note": note,
                },
            )
            pending_actions.append(card)
            return {"status": "awaiting_user_confirmation", "preview": card["summary"]}

        return {"error": f"Unknown proposal tool: {tool_name}"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Confirmed Action Executor (Audited DB Mutations)
# ---------------------------------------------------------------------------
def execute_signed_action(db: Session, owner: User, action_token: str) -> dict[str, Any]:
    """Verify signed action token and atomically execute the audited mutation."""
    body = verify_action_token(action_token, owner.id)
    action_type = body["action_type"]
    p = body["payload"]
    audit_reason = "Applied via LOOMOS AI Copilot"

    if action_type == "add_looms":
        created = []
        for offset in range(int(p["count"])):
            num = f"{p['prefix']}{int(p['start_number']) + offset:02d}"
            if db.scalar(select(Loom.id).where(Loom.loom_number == num)):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Loom {num} already exists")
            loom = Loom(
                loom_number=num,
                loom_type=p["loom_type"],
                make_model=p.get("make_model", ""),
                rated_rpm=int(p["rated_rpm"]),
                reed_space_in=int(p["reed_space_in"]),
                status="OPERATIONAL",
                created_by=owner.id,
            )
            db.add(loom)
            created.append(loom)
        db.flush()
        for loom in created:
            record_audit(
                db,
                entity_type="loom",
                entity_id=loom.id,
                action="CREATE",
                changed_by=owner.id,
                new_values=snapshot_fields(loom, ["loom_number", "loom_type", "rated_rpm"]),
                reason=audit_reason,
            )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "created_ids": [l.id for l in created]}

    if action_type == "update_loom":
        loom = db.get(Loom, int(p["loom_id"]))
        if not loom:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loom not found")
        fields = ["loom_number", "loom_type", "make_model", "rated_rpm", "reed_space_in", "status", "is_active"]
        old = snapshot_fields(loom, fields)
        for k, v in p["updates"].items():
            if k in fields:
                setattr(loom, k, v)
        record_audit(
            db,
            entity_type="loom",
            entity_id=loom.id,
            action="UPDATE",
            changed_by=owner.id,
            old_values=old,
            new_values=snapshot_fields(loom, fields),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": loom.id}

    if action_type == "record_advance":
        weaver = db.get(Weaver, int(p["weaver_id"]))
        if not weaver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weaver not found")
        adv = Advance(
            weaver_id=weaver.id,
            advance_date=date.fromisoformat(p["advance_date"]),
            amount_paise=int(p["amount_paise"]),
            note=p.get("note"),
            created_by=owner.id,
        )
        db.add(adv)
        db.flush()
        record_audit(
            db,
            entity_type="advance",
            entity_id=adv.id,
            action="CREATE",
            changed_by=owner.id,
            new_values=snapshot_fields(adv, ["weaver_id", "advance_date", "amount_paise"]),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": adv.id}

    if action_type == "record_expense":
        exp = Expense(
            expense_date=date.fromisoformat(p["expense_date"]),
            category=p["category"],
            amount_paise=int(p["amount_paise"]),
            note=p.get("note"),
            created_by=owner.id,
        )
        db.add(exp)
        db.flush()
        record_audit(
            db,
            entity_type="expense",
            entity_id=exp.id,
            action="CREATE",
            changed_by=owner.id,
            new_values=snapshot_fields(exp, ["expense_date", "category", "amount_paise"]),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": exp.id}

    if action_type == "record_trader_payment":
        trader = db.get(Trader, int(p["trader_id"]))
        if not trader:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")
        pay = TraderPayment(
            trader_id=trader.id,
            payment_date=date.fromisoformat(p["payment_date"]),
            amount_paise=int(p["amount_paise"]),
            shortage_deduction_paise=int(p.get("shortage_deduction_paise") or 0),
            reference=p.get("reference"),
            created_by=owner.id,
        )
        db.add(pay)
        db.flush()
        record_audit(
            db,
            entity_type="trader_payment",
            entity_id=pay.id,
            action="CREATE",
            changed_by=owner.id,
            new_values=snapshot_fields(pay, ["trader_id", "payment_date", "amount_paise", "shortage_deduction_paise"]),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": pay.id}

    if action_type == "create_delivery":
        trader = db.get(Trader, int(p["trader_id"]))
        if not trader:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")
        items_in = p["items"]
        total_m = sum((Decimal(str(it["metres"])) for it in items_in), Decimal("0.00")).quantize(Decimal("0.01"))
        delivery = Delivery(
            trader_id=trader.id,
            challan_no=p["challan_no"],
            delivery_date=date.fromisoformat(p["delivery_date"]),
            total_metres=total_m,
            source="AI_COPILOT",
            created_by=owner.id,
        )
        db.add(delivery)
        db.flush()
        total_under = 0
        for it in items_in:
            sort_obj = db.get(FabricSort, int(it["sort_id"])) if it.get("sort_id") else None
            metres = Decimal(str(it["metres"])).quantize(Decimal("0.01"))
            rate_p = int(it["applied_rate_paise"])
            db.add(
                DeliveryItem(
                    delivery_id=delivery.id,
                    sort_id=sort_obj.id if sort_obj else None,
                    pieces=int(it.get("pieces") or 1),
                    metres=metres,
                    applied_rate_paise=rate_p,
                    created_by=owner.id,
                )
            )
            if sort_obj and rate_p < sort_obj.agreed_rate_paise:
                total_under += int((metres * Decimal(sort_obj.agreed_rate_paise - rate_p)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        record_audit(
            db,
            entity_type="delivery",
            entity_id=delivery.id,
            action="CREATE",
            changed_by=owner.id,
            new_values=snapshot_fields(delivery, ["trader_id", "challan_no", "delivery_date", "total_metres"]),
            reason=audit_reason,
        )
        if total_under > 0:
            db.add(
                Alert(
                    alert_type="RATE_UNDERPAYMENT",
                    severity="CRITICAL",
                    message=(
                        f"Challan {delivery.challan_no} ({trader.company_name}): paid below agreed sort rate! "
                        f"Shortfall = ₹{total_under / 100:.2f}."
                    )[:255],
                    status="OPEN",
                )
            )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": delivery.id}

    if action_type == "create_eb_bill":
        p_start = date.fromisoformat(p["period_start"])
        p_end = date.fromisoformat(p["period_end"])
        units = Decimal(str(p["units_consumed"])).quantize(Decimal("0.01"))
        net_p = int(p["net_bill_paise"])
        settings = db.scalar(select(UnitSettings).limit(1))
        plan = (
            db.scalar(
                select(EbTariffPlan)
                .options(selectinload(EbTariffPlan.slabs))
                .where(EbTariffPlan.id == settings.active_tariff_plan_id)
            )
            if (settings and settings.active_tariff_plan_id)
            else None
        )
        billing_days = max(1, (p_end - p_start).days)
        bd = (
            calculate_bill_breakdown_paise(
                units,
                plan,
                sanctioned_kw=settings.sanctioned_kw if settings else Decimal("10.00"),
                billing_days=billing_days,
            )
            if plan
            else {"energy_paise": 0, "fixed_paise": 0, "tax_paise": 0, "fppca_paise": 0}
        )
        bill = EbBill(
            tariff_plan_id=plan.id if plan else None,
            period_start=p_start,
            period_end=p_end,
            units_consumed=units,
            energy_paise=bd["energy_paise"],
            fixed_paise=bd["fixed_paise"],
            tax_paise=bd["tax_paise"],
            fppca_paise=bd["fppca_paise"],
            overhead_paise=max(0, net_p - bd["energy_paise"]),
            net_bill_paise=net_p,
            total_power_cut_mins=int(p.get("total_power_cut_mins") or 0),
            notes=p.get("notes"),
            created_by=owner.id,
        )
        db.add(bill)
        db.flush()
        record_audit(
            db,
            entity_type="eb_bill",
            entity_id=bill.id,
            action="CREATE",
            changed_by=owner.id,
            new_values=snapshot_fields(bill, ["period_start", "period_end", "units_consumed", "net_bill_paise"]),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": bill.id}

    if action_type == "update_sort_rate":
        srt = db.get(FabricSort, int(p["sort_id"]))
        if not srt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fabric sort not found")
        fields = ["agreed_rate_paise", "wastage_pct", "expected_weft_kg_per_100m"]
        old = snapshot_fields(srt, fields)
        u = p["updates"]
        if "agreed_rate_paise" in u:
            srt.agreed_rate_paise = int(u["agreed_rate_paise"])
        if "wastage_pct" in u:
            srt.wastage_pct = Decimal(str(u["wastage_pct"]))
        if "expected_weft_kg_per_100m" in u:
            srt.expected_weft_kg_per_100m = Decimal(str(u["expected_weft_kg_per_100m"]))
        record_audit(
            db,
            entity_type="fabric_sort",
            entity_id=srt.id,
            action="UPDATE",
            changed_by=owner.id,
            old_values=old,
            new_values=snapshot_fields(srt, fields),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": srt.id}

    if action_type == "save_shift_entries":
        settings = db.scalar(select(UnitSettings).limit(1))
        planned_mins = settings.planned_shift_mins if settings else 600
        e_date = date.fromisoformat(p["entry_date"])
        shift_no = int(p["shift_no"])
        touched_beams: set[int] = set()
        saved_ids: list[int] = []
        for r in p["rows"]:
            loom_id = int(r["loom_id"])
            weaver_id = int(r["weaver_id"])
            beam_id = int(r["beam_id"]) if r.get("beam_id") is not None else None
            net_m = Decimal(str(r["net_metres"])).quantize(Decimal("0.01"))
            pc = int(r.get("power_cut_mins") or 0)
            dt = int(r.get("downtime_mins") or 0)
            dm = Decimal(str(r.get("defective_metres") or 0)).quantize(Decimal("0.01"))
            notes = r.get("notes")

            slot_stmt = select(ShiftEntry).where(
                ShiftEntry.loom_id == loom_id,
                ShiftEntry.entry_date == e_date,
                ShiftEntry.shift_no == shift_no,
                ShiftEntry.is_deleted.is_(False),
            )
            slot_stmt = slot_stmt.where(ShiftEntry.beam_id == beam_id if beam_id is not None else ShiftEntry.beam_id.is_(None))
            existing = db.scalar(slot_stmt)
            if existing:
                old = snapshot_fields(existing, ["weaver_id", "net_metres", "power_cut_mins", "downtime_mins", "defective_metres"])
                existing.weaver_id = weaver_id
                existing.net_metres = net_m
                existing.power_cut_mins = pc
                existing.downtime_mins = dt
                existing.defective_metres = dm
                existing.notes = notes
                record_audit(
                    db,
                    entity_type="shift_entry",
                    entity_id=existing.id,
                    action="UPDATE",
                    changed_by=owner.id,
                    old_values=old,
                    new_values=snapshot_fields(existing, ["weaver_id", "net_metres", "power_cut_mins", "downtime_mins", "defective_metres"]),
                    reason=audit_reason,
                )
                saved_ids.append(existing.id)
            else:
                entry = ShiftEntry(
                    client_uuid=f"ai-{uuid.uuid4().hex}",
                    loom_id=loom_id,
                    weaver_id=weaver_id,
                    beam_id=beam_id,
                    entry_date=e_date,
                    shift_no=shift_no,
                    entry_mode="DIRECT",
                    net_metres=net_m,
                    planned_mins=planned_mins,
                    power_cut_mins=pc,
                    downtime_mins=dt,
                    defective_metres=dm,
                    notes=notes,
                    created_by=owner.id,
                )
                db.add(entry)
                db.flush()
                record_audit(
                    db,
                    entity_type="shift_entry",
                    entity_id=entry.id,
                    action="CREATE",
                    changed_by=owner.id,
                    new_values=snapshot_fields(entry, ["loom_id", "weaver_id", "beam_id", "entry_date", "shift_no", "net_metres"]),
                    reason=audit_reason,
                )
                saved_ids.append(entry.id)
            if beam_id:
                touched_beams.add(beam_id)
        for bid in touched_beams:
            sync_weft_wastage_alert(db, bid)
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "ids": saved_ids}

    if action_type == "update_unit_settings":
        unit = db.scalar(select(UnitSettings).limit(1))
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit settings not found")
        fields = ["unit_name", "location", "shifts_per_day", "planned_shift_mins", "sanctioned_kw"]
        old = snapshot_fields(unit, fields)
        u = p["updates"]
        for k, v in u.items():
            if k == "sanctioned_kw":
                unit.sanctioned_kw = Decimal(str(v))
            elif k in fields:
                setattr(unit, k, v)
        record_audit(
            db,
            entity_type="unit_settings",
            entity_id=unit.id,
            action="UPDATE",
            changed_by=owner.id,
            old_values=old,
            new_values=snapshot_fields(unit, fields),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": unit.id}

    if action_type == "update_alert":
        alert = db.get(Alert, int(p["alert_id"]))
        if not alert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        old = snapshot_fields(alert, ["status"])
        alert.status = p["status"]
        record_audit(
            db,
            entity_type="alert",
            entity_id=alert.id,
            action="UPDATE",
            changed_by=owner.id,
            old_values=old,
            new_values=snapshot_fields(alert, ["status"]),
            reason=audit_reason,
        )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": alert.id}

    if action_type == "set_calendar_day":
        cal_date = date.fromisoformat(p["calendar_date"])
        row = db.scalar(select(ShedCalendar).where(ShedCalendar.calendar_date == cal_date))
        if row:
            old = snapshot_fields(row, ["is_working_day", "planned_shifts", "note"])
            row.is_working_day = bool(p["is_working_day"])
            row.planned_shifts = int(p["planned_shifts"])
            row.note = p.get("note")
            record_audit(
                db,
                entity_type="shed_calendar",
                entity_id=row.id,
                action="UPDATE",
                changed_by=owner.id,
                old_values=old,
                new_values=snapshot_fields(row, ["is_working_day", "planned_shifts", "note"]),
                reason=audit_reason,
            )
        else:
            row = ShedCalendar(
                calendar_date=cal_date,
                is_working_day=bool(p["is_working_day"]),
                planned_shifts=int(p["planned_shifts"]),
                note=p.get("note"),
                created_by=owner.id,
            )
            db.add(row)
            db.flush()
            record_audit(
                db,
                entity_type="shed_calendar",
                entity_id=row.id,
                action="CREATE",
                changed_by=owner.id,
                new_values=snapshot_fields(row, ["calendar_date", "is_working_day", "planned_shifts"]),
                reason=audit_reason,
            )
        db.commit()
        return {"status": "executed", "action_type": action_type, "summary": body["summary"], "id": row.id}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported action type: {action_type}")


# ---------------------------------------------------------------------------
# Gemini Tool Declarations & Orchestration Loop
# ---------------------------------------------------------------------------
def _build_tool_declarations(types_mod: Any) -> list[Any]:
    S = types_mod.Schema
    T = types_mod.Type
    FD = types_mod.FunctionDeclaration
    return [
        # --- READ TOOLS ---
        FD(
            name="get_shed_summary",
            description="Get live LOOMOS shed overview: today's metres, period metres, loom OEE/utilization, active looms, open alerts, and complete P&L (revenue, wages, EB, expenses, net profit, receivables, rate underpayment).",
            parameters=S(type=T.OBJECT, properties={"days": S(type=T.INTEGER, description="Lookback period in days (default 30).")}),
        ),
        FD(
            name="list_looms",
            description="List all looms with loom_number, loom_type, rated_rpm, reed_space_in, status, and currently loaded beam/sort.",
            parameters=S(type=T.OBJECT, properties={"include_inactive": S(type=T.BOOLEAN)}),
        ),
        FD(
            name="list_beams_and_etas",
            description="List all warp beams (RUNNING, IN_STOCK, COMPLETED), remaining metres, weft wastage %, and live P50/P75/P25 completion ETAs.",
            parameters=S(type=T.OBJECT, properties={}),
        ),
        FD(
            name="list_weavers_and_payroll",
            description="List all active weavers/helpers/fitters, their active wage rules, recent 30-day advances, and live payroll preview for the last N days.",
            parameters=S(type=T.OBJECT, properties={"days": S(type=T.INTEGER, description="Payroll preview lookback days (default 7).")}),
        ),
        FD(
            name="list_traders_and_sorts",
            description="List all traders with live receivable balances & rate-cut shortfalls, plus all fabric sorts with agreed ₹/m conversion rates and weft wastage limits.",
            parameters=S(type=T.OBJECT, properties={}),
        ),
        FD(
            name="get_eb_overview",
            description="Get TNPDCL EB bills, bi-monthly bill prediction, 30-day power-cut loss, kWh/metre efficiency & anomaly flags. Optionally estimate EB for target metres or calculate exact TNPDCL slab bill for a kWh value.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "estimate_metres": S(type=T.NUMBER, description="Optional target cloth metres to estimate EB bill for."),
                    "calc_units_kwh": S(type=T.NUMBER, description="Optional kWh units to compute exact TNPDCL slab bill for."),
                },
            ),
        ),
        FD(
            name="get_recent_shifts_and_anomalies",
            description="Get recent daily shift entries (date, shift, loom, weaver, metres, power cut, downtime, defects) and detected production anomalies.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "days": S(type=T.INTEGER, description="Days to look back (default 7)."),
                    "loom_number": S(type=T.STRING, description="Optional loom number filter, e.g. L-03."),
                },
            ),
        ),
        FD(
            name="get_recent_deliveries_and_expenses",
            description="Get recent grey cloth delivery challans (with rate-cut shortfalls), recent trader payments, and recent shed expenses.",
            parameters=S(type=T.OBJECT, properties={"limit": S(type=T.INTEGER, description="Max rows per section (default 12).")}),
        ),
        FD(
            name="get_weekly_forecast_and_alerts",
            description="Get 5-week walk-forward production forecast (CN-MA vs Holt vs Naive) and all open LOOMOS alerts.",
            parameters=S(type=T.OBJECT, properties={}),
        ),
        FD(
            name="get_recent_inspections",
            description="Get recent Cloth AI defect inspection records and confidence scores.",
            parameters=S(type=T.OBJECT, properties={"limit": S(type=T.INTEGER)}),
        ),
        # --- SAFE WRITE PROPOSAL TOOLS (ALWAYS SHOW CONFIRM/CANCEL CARD FIRST) ---
        FD(
            name="propose_add_looms",
            description="Propose adding 1 or more new looms to the shed (creates a safe Confirm/Cancel preview card).",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "count": S(type=T.INTEGER, description="Number of looms to add (1-100)."),
                    "prefix": S(type=T.STRING, description="Prefix like 'L-' or 'R-' (default 'L-')."),
                    "start_number": S(type=T.INTEGER, description="Optional starting number; auto-calculated if omitted."),
                    "loom_type": S(type=T.STRING, description="SHUTTLE, RAPIER, AIRJET, WATERJET, or PROJECTILE."),
                    "make_model": S(type=T.STRING),
                    "rated_rpm": S(type=T.INTEGER, description="Rated RPM (default 160)."),
                    "reed_space_in": S(type=T.INTEGER, description="Reed space inches (default 56)."),
                },
                required=["count"],
            ),
        ),
        FD(
            name="propose_update_loom",
            description="Propose updating an existing loom's status (OPERATIONAL / UNDER_MAINTENANCE / IDLE), RPM, model, or active flag.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "loom_number": S(type=T.STRING, description="Loom number, e.g. L-03."),
                    "status": S(type=T.STRING, description="OPERATIONAL, UNDER_MAINTENANCE, or IDLE."),
                    "rated_rpm": S(type=T.INTEGER),
                    "make_model": S(type=T.STRING),
                    "is_active": S(type=T.BOOLEAN),
                },
                required=["loom_number"],
            ),
        ),
        FD(
            name="propose_record_advance",
            description="Propose recording a cash advance (uthaav) given to a weaver/helper.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "weaver_name": S(type=T.STRING, description="Worker name (fuzzy matched)."),
                    "amount_rupees": S(type=T.NUMBER, description="Amount in Indian Rupees (e.g. 2000)."),
                    "advance_date": S(type=T.STRING, description="YYYY-MM-DD (defaults to today IST)."),
                    "note": S(type=T.STRING),
                },
                required=["weaver_name", "amount_rupees"],
            ),
        ),
        FD(
            name="propose_record_expense",
            description="Propose recording an operational shed expense (spares, oil, repairs, rent, etc.).",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "category": S(type=T.STRING, description="Expense category, e.g. Spares, Oil, Repair, Rent."),
                    "amount_rupees": S(type=T.NUMBER, description="Amount in Indian Rupees."),
                    "expense_date": S(type=T.STRING, description="YYYY-MM-DD (defaults to today IST)."),
                    "note": S(type=T.STRING),
                },
                required=["category", "amount_rupees"],
            ),
        ),
        FD(
            name="propose_record_trader_payment",
            description="Propose recording a payment received from a trader.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "trader_name": S(type=T.STRING, description="Trader company name (fuzzy matched)."),
                    "amount_rupees": S(type=T.NUMBER, description="Amount received in Rupees."),
                    "payment_date": S(type=T.STRING, description="YYYY-MM-DD (defaults to today IST)."),
                    "shortage_deduction_rupees": S(type=T.NUMBER, description="Optional deduction in Rupees."),
                    "reference": S(type=T.STRING, description="UPI/NEFT/Cash reference."),
                },
                required=["trader_name", "amount_rupees"],
            ),
        ),
        FD(
            name="propose_create_delivery",
            description="Propose creating a grey cloth delivery challan (checks for trader rate cuts automatically). Great for logging scanned challan photos.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "trader_name": S(type=T.STRING),
                    "challan_no": S(type=T.STRING),
                    "delivery_date": S(type=T.STRING, description="YYYY-MM-DD (defaults to today IST)."),
                    "items": S(
                        type=T.ARRAY,
                        items=S(
                            type=T.OBJECT,
                            properties={
                                "sort_name": S(type=T.STRING),
                                "metres": S(type=T.NUMBER),
                                "applied_rate_rupees": S(type=T.NUMBER),
                                "pieces": S(type=T.INTEGER),
                            },
                            required=["metres"],
                        ),
                    ),
                },
                required=["trader_name", "challan_no", "items"],
            ),
        ),
        FD(
            name="propose_create_eb_bill",
            description="Propose logging a TNPDCL bi-monthly electricity bill (great after reading an EB bill photo).",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "period_start": S(type=T.STRING, description="YYYY-MM-DD"),
                    "period_end": S(type=T.STRING, description="YYYY-MM-DD"),
                    "units_consumed": S(type=T.NUMBER, description="Units in kWh"),
                    "net_bill_rupees": S(type=T.NUMBER, description="Total payable bill in Rupees"),
                    "total_power_cut_mins": S(type=T.INTEGER),
                    "notes": S(type=T.STRING),
                },
                required=["period_start", "period_end", "units_consumed", "net_bill_rupees"],
            ),
        ),
        FD(
            name="propose_update_sort_rate",
            description="Propose updating a fabric sort's agreed conversion rate (₹/m), wastage limit %, or expected weft kg/100m.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "sort_name": S(type=T.STRING),
                    "agreed_rate_rupees": S(type=T.NUMBER),
                    "wastage_pct": S(type=T.NUMBER),
                    "expected_weft_kg_per_100m": S(type=T.NUMBER),
                },
                required=["sort_name"],
            ),
        ),
        FD(
            name="propose_save_shift_entries",
            description="Propose logging or updating daily shift production entries for one or more looms.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "entry_date": S(type=T.STRING, description="YYYY-MM-DD (defaults to today IST)."),
                    "shift_no": S(type=T.INTEGER, description="Shift number 1, 2, or 3 (default 1)."),
                    "entries": S(
                        type=T.ARRAY,
                        items=S(
                            type=T.OBJECT,
                            properties={
                                "loom_number": S(type=T.STRING),
                                "net_metres": S(type=T.NUMBER),
                                "weaver_name": S(type=T.STRING),
                                "power_cut_mins": S(type=T.INTEGER),
                                "downtime_mins": S(type=T.INTEGER),
                                "defective_metres": S(type=T.NUMBER),
                                "notes": S(type=T.STRING),
                            },
                            required=["loom_number", "net_metres"],
                        ),
                    ),
                },
                required=["entries"],
            ),
        ),
        FD(
            name="propose_update_unit_settings",
            description="Propose updating shed unit settings (unit_name, location, shifts_per_day, planned_shift_mins, sanctioned_kw).",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "unit_name": S(type=T.STRING),
                    "location": S(type=T.STRING),
                    "shifts_per_day": S(type=T.INTEGER),
                    "planned_shift_mins": S(type=T.INTEGER),
                    "sanctioned_kw": S(type=T.NUMBER),
                },
            ),
        ),
        FD(
            name="propose_update_alert",
            description="Propose dismissing or acknowledging an open LOOMOS alert by ID.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "alert_id": S(type=T.INTEGER),
                    "status": S(type=T.STRING, description="ACKNOWLEDGED or DISMISSED"),
                },
                required=["alert_id"],
            ),
        ),
        FD(
            name="propose_set_calendar_day",
            description="Propose marking a date as a holiday (is_working_day=false) or custom shift day on the Shed Calendar.",
            parameters=S(
                type=T.OBJECT,
                properties={
                    "calendar_date": S(type=T.STRING, description="YYYY-MM-DD"),
                    "is_working_day": S(type=T.BOOLEAN),
                    "planned_shifts": S(type=T.INTEGER),
                    "note": S(type=T.STRING),
                },
                required=["calendar_date", "is_working_day"],
            ),
        ),
    ]


READ_TOOL_HANDLERS = {
    "get_shed_summary": _tool_get_shed_summary,
    "list_looms": _tool_list_looms,
    "list_beams_and_etas": _tool_list_beams_and_etas,
    "list_weavers_and_payroll": _tool_list_weavers_and_payroll,
    "list_traders_and_sorts": _tool_list_traders_and_sorts,
    "get_eb_overview": _tool_get_eb_overview,
    "get_recent_shifts_and_anomalies": _tool_get_recent_shifts_and_anomalies,
    "get_recent_deliveries_and_expenses": _tool_get_recent_deliveries_and_expenses,
    "get_weekly_forecast_and_alerts": _tool_get_forecast_and_alerts,
    "get_recent_inspections": _tool_get_recent_inspections,
}


def _system_instruction(owner: User, ui_lang: str) -> str:
    today = today_ist()
    return (
        f"You are **LOOMOS AI Copilot**, the private 24/7 operations & management assistant for {owner.full_name}'s "
        f"Tamil Nadu powerloom weaving shed inside LOOMOS.\n"
        f"Today's IST date: {today.isoformat()} ({today.strftime('%d/%m/%Y')}). UI language preference: {ui_lang}.\n\n"
        "Communication rules:\n"
        "- The owner often writes fast, casual, shortened English, typos, Tamil, or Tanglish (e.g. 'hw mch mtrs L3 tdy', "
        "'selvam ku 2k adv podu', 'eb bill scan panni add panu', 'chk rate cuts'). Understand intent seamlessly and NEVER lecture about spelling.\n"
        "- Reply in the same language style the user wrote in (English, Tamil, or clear friendly English/Tamil matching their prompt). Keep answers crisp, structured, mobile-friendly, with ₹ currency and DD/MM/YYYY dates.\n"
        "- ALWAYS call live read tools before quoting shed numbers, wages, metres, beams, EB, or balances. NEVER invent numbers.\n"
        "- Whenever the user asks to add, edit, log, record, update, or dismiss data (or uploads a photo of a TNPDCL EB bill, delivery challan, expense receipt, or handwritten shift register to log), ALWAYS call the matching `propose_*` tool so the UI renders a safe Confirm / Cancel card. Tell the user briefly to tap **Confirm & Apply** on the card.\n"
        "- If the user uploads a cloth defect photo, analyze visible weaving defects (broken pick, missing warp, oil stain, slub/knot, reed mark, hole, float) and give practical powerloom troubleshooting steps (shuttle tension, pirn/weft check, reed dent check, beam tension).\n"
        "- If an entity name is ambiguous or missing, use read tools to check available names and ask one short clarifying question."
    )


def _extract_visible_text(response: Any) -> str:
    """Extract only user-visible text parts (excluding internal thinking/thought parts)."""
    parts_out: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates and getattr(candidates[0], "content", None):
        for part in getattr(candidates[0].content, "parts", None) or []:
            if getattr(part, "thought", False):
                continue
            txt = getattr(part, "text", None)
            if txt:
                parts_out.append(txt)
    if parts_out:
        return "".join(parts_out).strip()
    try:
        return (response.text or "").strip()
    except Exception:
        return ""


def _build_genai_client(api_key: str) -> Any:
    from google import genai  # lazy import so tests without key stay fast
    from google.genai import types

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=25_000))


def _generate_with_fallback(
    client: Any,
    model_chain: list[str],
    contents: list[Any],
    config: Any,
) -> tuple[Any, str]:
    """Call Gemini with automatic fallback across configured models on 429/503/404 spikes."""
    last_exc: Exception | None = None
    for model_name in model_chain:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            return resp, model_name
        except Exception as exc:
            last_exc = exc
            msg = str(exc).upper()
            retryable = any(
                tok in msg
                for tok in ("429", "503", "500", "404", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "NOT_FOUND", "OVERLOADED", "TIMEOUT", "TIMED OUT")
            )
            if not retryable:
                raise
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"All Gemini models are temporarily busy ({str(last_exc)[:180]}). Please try again in a few seconds.",
    )


def run_copilot_chat(
    db: Session,
    owner: User,
    *,
    message: str,
    history: list[dict[str, str]] | None = None,
    mode: str = "fast",
    ui_lang: str = "en",
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
) -> dict[str, Any]:
    """Run a multimodal, tool-calling Gemini conversation turn against live LOOMOS data."""
    cfg = get_settings()
    if not cfg.is_ai_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LOOMOS AI Copilot is not configured (missing LOOMOS_GEMINI_API_KEY).",
        )

    from google.genai import types

    client = _build_genai_client(cfg.gemini_api_key.strip())
    model_chain = cfg.ai_model_chain(mode)
    tool_declarations = _build_tool_declarations(types)

    thinking_cfg = None
    if mode == "fast":
        try:
            thinking_cfg = types.ThinkingConfig(thinking_level="LOW")
        except Exception:
            thinking_cfg = None

    gen_config = types.GenerateContentConfig(
        system_instruction=_system_instruction(owner, ui_lang),
        tools=[types.Tool(function_declarations=tool_declarations)],
        temperature=0.3,
        thinking_config=thinking_cfg,
    )

    contents: list[Any] = []
    for item in (history or [])[-16:]:
        role = "model" if item.get("role") == "assistant" else "user"
        txt = str(item.get("content") or "").strip()
        if txt:
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=txt[:4000])]))

    user_parts: list[Any] = []
    if image_bytes and image_mime_type:
        user_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type))
    prompt_text = (message or "").strip() or (
        "Please analyze this uploaded image (EB bill, delivery challan, shift note, or cloth photo) and suggest the next step."
    )
    user_parts.append(types.Part.from_text(text=prompt_text))
    contents.append(types.Content(role="user", parts=user_parts))

    pending_actions: list[dict[str, Any]] = []
    tools_used: list[str] = []
    used_model = model_chain[0]

    for _round in range(MAX_TOOL_ROUNDS):
        response, used_model = _generate_with_fallback(client, model_chain, contents, gen_config)
        fcalls = getattr(response, "function_calls", None) or []
        if not fcalls:
            reply_text = _extract_visible_text(response)
            if not reply_text and pending_actions:
                reply_text = "Ready to apply — please review the preview card below and tap **Confirm & Apply**."
            return {
                "reply": reply_text or "Done.",
                "model_used": used_model,
                "tools_used": tools_used,
                "pending_actions": pending_actions,
            }

        # Preserve model's exact Content (including Gemini 3.x thought_signature)
        candidates = getattr(response, "candidates", None) or []
        if candidates and getattr(candidates[0], "content", None):
            contents.append(candidates[0].content)

        fn_response_parts = []
        for fc in fcalls:
            fn_name = fc.name
            fn_args = dict(fc.args or {})
            tools_used.append(fn_name)
            if fn_name in READ_TOOL_HANDLERS:
                try:
                    result_obj = READ_TOOL_HANDLERS[fn_name](db, fn_args)
                except Exception as exc:
                    result_obj = {"error": str(exc)}
            elif fn_name.startswith("propose_"):
                result_obj = _propose_action(db, owner, fn_name, fn_args, pending_actions)
            else:
                result_obj = {"error": f"Unknown tool '{fn_name}'"}

            fn_response_parts.append(
                types.Part.from_function_response(
                    name=fn_name,
                    response={"result": _json_safe(result_obj)},
                )
            )
        contents.append(types.Content(role="user", parts=fn_response_parts))

    # Fallback final synthesis if max tool rounds reached
    reply_text = _extract_visible_text(response) if "response" in locals() else ""
    return {
        "reply": reply_text or "I've gathered the details — please review any pending action cards below.",
        "model_used": used_model,
        "tools_used": tools_used,
        "pending_actions": pending_actions,
    }
