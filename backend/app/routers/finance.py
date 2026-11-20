"""Owner-only deliveries with trader rate-cut alerts, payments, expenses, EB ledger & alerts."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit, snapshot_fields, soft_delete_record
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import (
    Alert,
    Delivery,
    DeliveryItem,
    EbBill,
    EbReading,
    EbTariffPlan,
    Expense,
    FabricSort,
    Trader,
    TraderPayment,
    UnitSettings,
    User,
)
from app.schemas.step1 import SoftDeleteRequest
from app.schemas.step2 import (
    AlertResponse,
    AlertUpdate,
    DeliveryCreate,
    DeliveryResponse,
    EbBillCreate,
    EbBillResponse,
    EbReadingCreate,
    EbReadingResponse,
    ExpenseCreate,
    ExpenseResponse,
    TraderLedgerSummary,
    TraderPaymentCreate,
    TraderPaymentResponse,
)
from app.services.eb_calculator import calculate_bill_breakdown_paise

router = APIRouter(prefix="/api/v1", tags=["finance"])


def _hydrate_deliveries(db: Session, deliveries: list[Delivery]) -> list[DeliveryResponse]:
    if not deliveries:
        return []
    del_ids = [d.id for d in deliveries]
    traders = {t.id: t.company_name for t in db.scalars(select(Trader)).all()}
    sorts = {s.id: s for s in db.scalars(select(FabricSort)).all()}
    all_items = db.scalars(
        select(DeliveryItem).where(DeliveryItem.delivery_id.in_(del_ids), DeliveryItem.is_deleted.is_(False))
    ).all()
    items_by_del: dict[int, list[DeliveryItem]] = defaultdict(list)
    for it in all_items:
        items_by_del[it.delivery_id].append(it)

    out: list[DeliveryResponse] = []
    for d in deliveries:
        item_resps = []
        tot_amt = 0
        tot_under = 0
        for it in items_by_del[d.id]:
            s = sorts.get(it.sort_id) if it.sort_id else None
            agreed = s.agreed_rate_paise if s else None
            amt = int((it.metres * Decimal(it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            under = 0
            if agreed is not None and it.applied_rate_paise < agreed:
                under = int(
                    (it.metres * Decimal(agreed - it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
            tot_amt += amt
            tot_under += under
            item_resps.append(
                {
                    "id": it.id,
                    "beam_id": it.beam_id,
                    "sort_id": it.sort_id,
                    "sort_name": s.sort_name if s else None,
                    "agreed_rate_paise": agreed,
                    "pieces": it.pieces,
                    "metres": it.metres,
                    "applied_rate_paise": it.applied_rate_paise,
                    "underpayment_paise": under,
                    "production_start_date": it.production_start_date,
                    "production_end_date": it.production_end_date,
                    "is_opening_stock": it.is_opening_stock,
                }
            )
        out.append(
            DeliveryResponse(
                id=d.id,
                trader_id=d.trader_id,
                trader_name=traders.get(d.trader_id, f"Trader #{d.trader_id}"),
                challan_no=d.challan_no,
                delivery_date=d.delivery_date,
                total_metres=d.total_metres,
                source=d.source,
                is_deleted=d.is_deleted,
                total_amount_paise=tot_amt,
                total_underpayment_paise=tot_under,
                has_rate_cut=tot_under > 0,
                items=item_resps,  # type: ignore[arg-type]
            )
        )
    return out


# ---------------------------------------------------------------------------
# Deliveries & Automated Trader Rate Checker
# ---------------------------------------------------------------------------
@router.get("/deliveries", response_model=list[DeliveryResponse])
def list_deliveries(
    trader_id: int | None = None,
    include_deleted: bool = False,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[DeliveryResponse]:
    stmt = select(Delivery).order_by(Delivery.delivery_date.desc(), Delivery.id.desc())
    if not include_deleted:
        stmt = stmt.where(Delivery.is_deleted.is_(False))
    if trader_id is not None:
        stmt = stmt.where(Delivery.trader_id == trader_id)
    return _hydrate_deliveries(db, db.scalars(stmt).all())


@router.post("/deliveries", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
def create_delivery(
    payload: DeliveryCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> DeliveryResponse:
    trader = db.get(Trader, payload.trader_id)
    if not trader:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")

    total_m = sum((it.metres for it in payload.items), Decimal("0.00")).quantize(Decimal("0.01"))
    delivery = Delivery(
        trader_id=payload.trader_id,
        challan_no=payload.challan_no.strip(),
        delivery_date=payload.delivery_date,
        total_metres=total_m,
        source="MANUAL",
        created_by=owner.id,
    )
    db.add(delivery)
    db.flush()

    total_under = 0
    for it in payload.items:
        sort_obj = db.get(FabricSort, it.sort_id) if it.sort_id else None
        if it.sort_id and not sort_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fabric sort {it.sort_id} not found")
        row = DeliveryItem(
            delivery_id=delivery.id,
            beam_id=it.beam_id,
            sort_id=it.sort_id,
            pieces=it.pieces,
            metres=it.metres,
            applied_rate_paise=it.applied_rate_paise,
            production_start_date=it.production_start_date,
            production_end_date=it.production_end_date,
            is_opening_stock=it.is_opening_stock,
            created_by=owner.id,
        )
        db.add(row)
        if sort_obj and it.applied_rate_paise < sort_obj.agreed_rate_paise:
            total_under += int(
                (it.metres * Decimal(sort_obj.agreed_rate_paise - it.applied_rate_paise)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )

    record_audit(
        db,
        entity_type="delivery",
        entity_id=delivery.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(delivery, ["trader_id", "challan_no", "delivery_date", "total_metres"]),
    )
    if total_under > 0:
        msg = (
            f"Challan {delivery.challan_no} ({trader.company_name}): paid below agreed sort rate! "
            f"Shortfall = ₹{total_under / 100:.2f}."
        )[:255]
        db.add(
            Alert(
                alert_type="RATE_UNDERPAYMENT",
                severity="CRITICAL",
                message=msg,
                status="OPEN",
            )
        )
    db.commit()
    return _hydrate_deliveries(db, [delivery])[0]


@router.delete("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def soft_delete_delivery(
    delivery_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> DeliveryResponse:
    d = db.get(Delivery, delivery_id)
    if not d or d.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    soft_delete_record(
        db,
        obj=d,
        entity_type="delivery",
        entity_id=d.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["trader_id", "challan_no", "delivery_date", "total_metres"],
    )
    items = db.scalars(
        select(DeliveryItem).where(DeliveryItem.delivery_id == d.id, DeliveryItem.is_deleted.is_(False))
    ).all()
    for it in items:
        it.is_deleted = True
        it.deleted_at = d.deleted_at
        it.deleted_by = owner.id
        it.delete_reason = payload.reason.strip()
    trader = db.get(Trader, d.trader_id)
    prefix = f"Challan {d.challan_no} ({trader.company_name}):" if trader else f"Challan {d.challan_no} ("
    matching_alerts = db.scalars(
        select(Alert).where(
            Alert.alert_type == "RATE_UNDERPAYMENT",
            Alert.status == "OPEN",
        )
    ).all()
    for al in matching_alerts:
        if al.message.startswith(prefix):
            al.status = "DISMISSED"
    db.commit()
    return _hydrate_deliveries(db, [d])[0]


# ---------------------------------------------------------------------------
# Trader Payments & Receivable Ledger
# ---------------------------------------------------------------------------
@router.get("/payments", response_model=list[TraderPaymentResponse])
def list_payments(
    trader_id: int | None = None,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[TraderPaymentResponse]:
    stmt = select(TraderPayment).where(TraderPayment.is_deleted.is_(False)).order_by(TraderPayment.payment_date.desc(), TraderPayment.id.desc())
    if trader_id is not None:
        stmt = stmt.where(TraderPayment.trader_id == trader_id)
    traders = {t.id: t.company_name for t in db.scalars(select(Trader)).all()}
    out = []
    for p in db.scalars(stmt).all():
        r = TraderPaymentResponse.model_validate(p)
        r.trader_name = traders.get(p.trader_id)
        out.append(r)
    return out


@router.post("/payments", response_model=TraderPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: TraderPaymentCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> TraderPaymentResponse:
    trader = db.get(Trader, payload.trader_id)
    if not trader:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")
    pay = TraderPayment(
        trader_id=payload.trader_id,
        payment_date=payload.payment_date,
        amount_paise=payload.amount_paise,
        shortage_deduction_paise=payload.shortage_deduction_paise,
        reference=payload.reference,
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
    )
    db.commit()
    db.refresh(pay)
    res = TraderPaymentResponse.model_validate(pay)
    res.trader_name = trader.company_name
    return res


@router.delete("/payments/{payment_id}", response_model=TraderPaymentResponse)
def soft_delete_payment(
    payment_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> TraderPaymentResponse:
    pay = db.get(TraderPayment, payment_id)
    if not pay or pay.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    soft_delete_record(
        db,
        obj=pay,
        entity_type="trader_payment",
        entity_id=pay.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["trader_id", "payment_date", "amount_paise"],
    )
    db.commit()
    db.refresh(pay)
    return TraderPaymentResponse.model_validate(pay)


@router.get("/traders/ledger", response_model=list[TraderLedgerSummary])
def get_traders_ledger(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TraderLedgerSummary]:
    traders = db.scalars(select(Trader).order_by(Trader.company_name)).all()
    deliveries = _hydrate_deliveries(
        db, db.scalars(select(Delivery).where(Delivery.is_deleted.is_(False))).all()
    )
    payments = db.scalars(select(TraderPayment).where(TraderPayment.is_deleted.is_(False))).all()

    by_t_metres: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    by_t_billed: dict[int, int] = defaultdict(int)
    by_t_under: dict[int, int] = defaultdict(int)
    for d in deliveries:
        by_t_metres[d.trader_id] += d.total_metres
        by_t_billed[d.trader_id] += d.total_amount_paise
        by_t_under[d.trader_id] += d.total_underpayment_paise

    by_t_rec: dict[int, int] = defaultdict(int)
    by_t_short: dict[int, int] = defaultdict(int)
    for p in payments:
        by_t_rec[p.trader_id] += p.amount_paise
        by_t_short[p.trader_id] += p.shortage_deduction_paise

    return [
        TraderLedgerSummary(
            trader_id=t.id,
            company_name=t.company_name,
            total_metres=by_t_metres[t.id],
            billed_paise=by_t_billed[t.id],
            received_paise=by_t_rec[t.id],
            shortage_paise=by_t_short[t.id],
            balance_paise=by_t_billed[t.id] - by_t_rec[t.id] - by_t_short[t.id],
            underpayment_paise=by_t_under[t.id],
        )
        for t in traders
    ]


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
@router.get("/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ExpenseResponse]:
    rows = db.scalars(
        select(Expense).where(Expense.is_deleted.is_(False)).order_by(Expense.expense_date.desc(), Expense.id.desc())
    ).all()
    return [ExpenseResponse.model_validate(e) for e in rows]


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> ExpenseResponse:
    exp = Expense(
        expense_date=payload.expense_date,
        category=payload.category.strip(),
        amount_paise=payload.amount_paise,
        note=payload.note,
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
    )
    db.commit()
    db.refresh(exp)
    return ExpenseResponse.model_validate(exp)


@router.delete("/expenses/{expense_id}", response_model=ExpenseResponse)
def soft_delete_expense(
    expense_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> ExpenseResponse:
    exp = db.get(Expense, expense_id)
    if not exp or exp.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    soft_delete_record(
        db,
        obj=exp,
        entity_type="expense",
        entity_id=exp.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["expense_date", "category", "amount_paise"],
    )
    db.commit()
    db.refresh(exp)
    return ExpenseResponse.model_validate(exp)


# ---------------------------------------------------------------------------
# EB Readings & Itemized EB Bills
# ---------------------------------------------------------------------------
@router.get("/eb-readings", response_model=list[EbReadingResponse])
def list_eb_readings(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[EbReadingResponse]:
    rows = db.scalars(
        select(EbReading).where(EbReading.is_deleted.is_(False)).order_by(EbReading.reading_date.desc(), EbReading.id.desc())
    ).all()
    return [EbReadingResponse.model_validate(r) for r in rows]


@router.post("/eb-readings", response_model=EbReadingResponse, status_code=status.HTTP_201_CREATED)
def create_eb_reading(
    payload: EbReadingCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> EbReadingResponse:
    row = EbReading(reading_date=payload.reading_date, kwh_total=payload.kwh_total, note=payload.note, created_by=owner.id)
    db.add(row)
    db.flush()
    record_audit(
        db,
        entity_type="eb_reading",
        entity_id=row.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(row, ["reading_date", "kwh_total"]),
    )
    db.commit()
    db.refresh(row)
    return EbReadingResponse.model_validate(row)


@router.delete("/eb-readings/{reading_id}", response_model=EbReadingResponse)
def soft_delete_eb_reading(
    reading_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> EbReadingResponse:
    row = db.get(EbReading, reading_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EB reading not found")
    soft_delete_record(
        db,
        obj=row,
        entity_type="eb_reading",
        entity_id=row.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["reading_date", "kwh_total"],
    )
    db.commit()
    db.refresh(row)
    return EbReadingResponse.model_validate(row)


@router.get("/eb-bills", response_model=list[EbBillResponse])
def list_eb_bills(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[EbBillResponse]:
    rows = db.scalars(
        select(EbBill).where(EbBill.is_deleted.is_(False)).order_by(EbBill.period_end.desc(), EbBill.id.desc())
    ).all()
    return [EbBillResponse.model_validate(b) for b in rows]


@router.post("/eb-bills", response_model=EbBillResponse, status_code=status.HTTP_201_CREATED)
def create_eb_bill(
    payload: EbBillCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> EbBillResponse:
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="period_end must be >= period_start")
    settings = db.scalar(select(UnitSettings).limit(1))
    plan_id = payload.tariff_plan_id or (settings.active_tariff_plan_id if settings else None)
    plan = (
        db.scalar(select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).where(EbTariffPlan.id == plan_id))
        if plan_id
        else None
    )

    billing_days = max(1, (payload.period_end - payload.period_start).days)
    breakdown = (
        calculate_bill_breakdown_paise(
            payload.units_consumed,
            plan,
            sanctioned_kw=settings.sanctioned_kw if settings else Decimal("10.00"),
            billing_days=billing_days,
        )
        if plan
        else {"energy_paise": 0, "fixed_paise": 0, "tax_paise": 0, "fppca_paise": 0}
    )

    energy_p = payload.energy_paise if payload.energy_paise is not None else breakdown["energy_paise"]
    fixed_p = payload.fixed_paise if payload.fixed_paise is not None else breakdown["fixed_paise"]
    tax_p = payload.tax_paise if payload.tax_paise is not None else breakdown["tax_paise"]
    fppca_p = payload.fppca_paise if payload.fppca_paise is not None else breakdown["fppca_paise"]
    overhead_p = max(0, payload.net_bill_paise - energy_p)

    bill = EbBill(
        tariff_plan_id=plan.id if plan else None,
        period_start=payload.period_start,
        period_end=payload.period_end,
        units_consumed=payload.units_consumed,
        energy_paise=energy_p,
        fixed_paise=fixed_p,
        tax_paise=tax_p,
        fppca_paise=fppca_p,
        subsidy_paise=payload.subsidy_paise,
        other_charges_paise=payload.other_charges_paise,
        overhead_paise=overhead_p,
        net_bill_paise=payload.net_bill_paise,
        total_power_cut_mins=payload.total_power_cut_mins,
        notes=payload.notes,
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
    )
    db.commit()
    db.refresh(bill)
    return EbBillResponse.model_validate(bill)


@router.delete("/eb-bills/{bill_id}", response_model=EbBillResponse)
def soft_delete_eb_bill(
    bill_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> EbBillResponse:
    bill = db.get(EbBill, bill_id)
    if not bill or bill.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EB bill not found")
    soft_delete_record(
        db,
        obj=bill,
        entity_type="eb_bill",
        entity_id=bill.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["period_start", "period_end", "units_consumed", "net_bill_paise"],
    )
    db.commit()
    db.refresh(bill)
    return EbBillResponse.model_validate(bill)


# ---------------------------------------------------------------------------
# Alerts (Dismissible, Explainable)
# ---------------------------------------------------------------------------
FINANCIAL_ALERT_TYPES = {"RATE_UNDERPAYMENT", "EB_OVERCHARGE", "EB_BILL"}


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[AlertResponse]:
    stmt = select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc())
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    if user.role != "OWNER":
        stmt = stmt.where(Alert.alert_type.not_in(FINANCIAL_ALERT_TYPES))
    return [AlertResponse.model_validate(a) for a in db.scalars(stmt.limit(100)).all()]


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
def update_alert_status(
    alert_id: int,
    payload: AlertUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertResponse:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if user.role != "OWNER" and alert.alert_type in FINANCIAL_ALERT_TYPES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required for financial alerts")
    old = snapshot_fields(alert, ["status"])
    alert.status = payload.status
    record_audit(
        db,
        entity_type="alert",
        entity_id=alert.id,
        action="UPDATE",
        changed_by=user.id,
        old_values=old,
        new_values=snapshot_fields(alert, ["status"]),
    )
    db.commit()
    db.refresh(alert)
    return AlertResponse.model_validate(alert)
