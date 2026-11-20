"""Safe isolated Demo Database CLI seeder (strictly writes ONLY to loomos_demo.db by default)."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DATA_DIR = BACKEND_ROOT / "data"
REAL_DB_PATH = (DATA_DIR / "loomos.db").resolve()
DEMO_DB_PATH = (DATA_DIR / "loomos_demo.db").resolve()


def _run_alembic_head(db_path: Path) -> None:
    alembic_ini = BACKEND_ROOT / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    os.environ["LOOMOS_DB_PATH"] = str(db_path)
    command.upgrade(cfg, "head")


def _reset_sqlite_file(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        p = Path(f"{db_path}{suffix}")
        if p.exists():
            p.unlink()
    _run_alembic_head(db_path)


def _backup_before_prod_reset() -> Path:
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"loomos_pre_reset_{stamp}.db"
    if REAL_DB_PATH.exists():
        src_conn = sqlite3.connect(str(REAL_DB_PATH))
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
    return dest


def populate_demo_shed(db_path: Path) -> dict[str, str | int]:
    """Populate loomos_demo.db with deterministic 20-loom shed data for Phase 1–5 testing."""
    _reset_sqlite_file(db_path)

    from app.core.audit import record_audit
    from app.core.database import build_engine
    from app.core.security import hash_password
    from app.models.core import (
        Advance,
        Alert,
        Beam,
        BeamLoading,
        DefectPrediction,
        Delivery,
        DeliveryItem,
        EbBill,
        EbReading,
        Expense,
        FabricSort,
        Inspection,
        Loom,
        Payslip,
        ShedCalendar,
        ShiftEntry,
        StopReason,
        Trader,
        TraderPayment,
        UnitSettings,
        User,
        WageRule,
        Weaver,
        WeaverAttendance,
        WeftReceipt,
    )
    from app.services.eb_calculator import calculate_energy_charge_paise
    from app.services.seed_defaults import seed_default_tariff_and_stops
    from app.services.vision_service import (
        MODEL_CARD_PATH,
        MODEL_PATH,
        SAMPLES_DIR,
        analyze_cloth_image_bytes,
        load_model_card,
    )

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    with SessionLocal() as db:
        owner = User(
            full_name="Ramasamy K (Demo Owner)",
            username="welcome123",
            password_hash=hash_password("welcome123"),
            role="OWNER",
            preferred_lang="en",
            is_active=True,
        )
        sup = User(
            full_name="Siva M (Demo Supervisor)",
            username="welcome@123",
            password_hash=hash_password("welcome@123"),
            role="SUPERVISOR",
            preferred_lang="en",
            is_active=True,
        )
        db.add_all([owner, sup])
        db.flush()

        tariff = seed_default_tariff_and_stops(db, owner.id)
        unit = UnitSettings(
            unit_name="LOOMOS",
            location="Palladam, Coimbatore TN",
            default_language="en",
            shifts_per_day=2,
            planned_shift_mins=600,
            shift_cutoff_hour=18,
            default_entry_mode="DIRECT",
            sanctioned_kw=Decimal("10.00"),
            active_tariff_plan_id=tariff.id,
            setup_completed_at=now_utc,
        )
        db.add(unit)

        # 5 Shuttle looms (S-01..S-05) for clean 5-loom testing & easy hand calculations
        rpms = [160, 160, 165, 165, 170]
        looms = []
        for idx in range(1, 6):
            l = Loom(
                loom_number=f"S-{idx:02d}",
                loom_type="SHUTTLE",
                make_model="G.K. Plain Shuttle 56\"",
                rated_rpm=rpms[idx - 1],
                reed_space_in=56,
                status="OPERATIONAL",
                is_active=True,
                created_by=owner.id,
            )
            looms.append(l)
        db.add_all(looms)
        db.flush()

        # Traders & Fabric Sorts
        t_murugan = Trader(
            company_name="Murugan Textiles",
            contact_name="Kumar",
            phone="9876543210",
            created_by=owner.id,
        )
        t_kaveri = Trader(
            company_name="Kaveri Mills",
            contact_name="Selvam",
            phone="9842211002",
            created_by=owner.id,
        )
        db.add_all([t_murugan, t_kaveri])
        db.flush()

        s_gada = FabricSort(
            sort_name="40s x 40s Grey Gada",
            warp_count="40s Cotton",
            weft_count="40s Cotton",
            reed=84,
            pick=76,
            width_in=Decimal("48.00"),
            agreed_rate_paise=600,
            expected_weft_kg_per_100m=Decimal("6.800"),
            wastage_pct=Decimal("2.50"),
            created_by=owner.id,
        )
        s_poplin = FabricSort(
            sort_name="30s Cotton Poplin",
            warp_count="30s Cotton",
            weft_count="30s Cotton",
            reed=72,
            pick=64,
            width_in=Decimal("44.00"),
            agreed_rate_paise=550,
            expected_weft_kg_per_100m=Decimal("7.200"),
            wastage_pct=Decimal("3.00"),
            created_by=owner.id,
        )
        db.add_all([s_gada, s_poplin])
        db.flush()

        # 4 Workers covering Weaver, Pirn Winder & Helper across all 4 Wage Modes
        w_arumugam = Weaver(
            full_name="Arumugam K",
            preferred_slip_lang="ta",
            role_type="WEAVER",
            phone="9894011111",
            created_by=owner.id,
        )
        w_ramesh = Weaver(
            full_name="Ramesh Kumar",
            preferred_slip_lang="hi",
            role_type="WEAVER",
            phone="9894022222",
            created_by=owner.id,
        )
        w_meena = Weaver(
            full_name="Meena Pirn Winder",
            preferred_slip_lang="en",
            role_type="PIRN_WINDER",
            phone="9894033333",
            created_by=owner.id,
        )
        w_lakshmi = Weaver(
            full_name="Lakshmi Helper",
            preferred_slip_lang="ta",
            role_type="HELPER",
            phone="9894044444",
            created_by=owner.id,
        )
        db.add_all([w_arumugam, w_ramesh, w_meena, w_lakshmi])
        db.flush()

        rule_start = today - timedelta(days=45)
        db.add_all([
            WageRule(weaver_id=w_arumugam.id, wage_mode="PER_LOOM_SHIFT", rate_paise=6000, effective_from=rule_start, created_by=owner.id),
            WageRule(weaver_id=w_ramesh.id, wage_mode="PER_METRE", rate_paise=400, effective_from=rule_start, created_by=owner.id),
            WageRule(weaver_id=w_meena.id, wage_mode="PER_SHIFT_ATTENDANCE", rate_paise=35000, effective_from=rule_start, created_by=owner.id),
            WageRule(weaver_id=w_lakshmi.id, wage_mode="FIXED_WEEKLY", rate_paise=250000, effective_from=rule_start, created_by=owner.id),
        ])

        # Warp Beams: BM-101..104 active on S-01..S-04; BM-105 in stock for S-05; BM-100 completed wastage sample
        b_101 = Beam(
            beam_no="BM-101",
            trader_id=t_murugan.id,
            sort_id=s_gada.id,
            received_date=today - timedelta(days=20),
            warp_length_m=Decimal("1000.00"),
            opening_woven_m=Decimal("0.00"),
            expected_tail_waste_m=Decimal("5.00"),
            due_date=today + timedelta(days=10),
            status="RUNNING",
            created_by=owner.id,
        )
        b_102 = Beam(
            beam_no="BM-102",
            trader_id=t_murugan.id,
            sort_id=s_gada.id,
            received_date=today - timedelta(days=18),
            warp_length_m=Decimal("1000.00"),
            opening_woven_m=Decimal("80.00"),
            expected_tail_waste_m=Decimal("5.00"),
            due_date=today + timedelta(days=8),
            status="RUNNING",
            created_by=owner.id,
        )
        b_103 = Beam(
            beam_no="BM-103",
            trader_id=t_kaveri.id,
            sort_id=s_poplin.id,
            received_date=today - timedelta(days=15),
            warp_length_m=Decimal("850.00"),
            opening_woven_m=Decimal("0.00"),
            expected_tail_waste_m=Decimal("4.00"),
            due_date=today + timedelta(days=12),
            status="RUNNING",
            created_by=owner.id,
        )
        b_104 = Beam(
            beam_no="BM-104",
            trader_id=t_kaveri.id,
            sort_id=s_poplin.id,
            received_date=today - timedelta(days=12),
            warp_length_m=Decimal("850.00"),
            opening_woven_m=Decimal("50.00"),
            expected_tail_waste_m=Decimal("4.00"),
            due_date=today + timedelta(days=14),
            status="RUNNING",
            created_by=owner.id,
        )
        b_100 = Beam(
            beam_no="BM-100",
            trader_id=t_kaveri.id,
            sort_id=s_poplin.id,
            received_date=today - timedelta(days=40),
            warp_length_m=Decimal("400.00"),
            opening_woven_m=Decimal("0.00"),
            expected_tail_waste_m=Decimal("5.00"),
            returned_weft_kg=Decimal("5.000"),
            status="COMPLETED",
            created_by=owner.id,
        )
        b_105 = Beam(
            beam_no="BM-105",
            trader_id=t_murugan.id,
            sort_id=s_gada.id,
            received_date=today - timedelta(days=2),
            warp_length_m=Decimal("800.00"),
            opening_woven_m=Decimal("0.00"),
            expected_tail_waste_m=Decimal("4.00"),
            due_date=today + timedelta(days=16),
            status="IN_STOCK",
            created_by=owner.id,
        )
        db.add_all([b_101, b_102, b_103, b_104, b_100, b_105])
        db.flush()

        # Mount BM-101..104 onto S-01..S-04; keep S-05 free for testing "Load on Loom" with BM-105
        db.add_all([
            BeamLoading(loom_id=looms[0].id, beam_id=b_101.id, loaded_at=now_utc - timedelta(days=20), created_by=owner.id),
            BeamLoading(loom_id=looms[1].id, beam_id=b_102.id, loaded_at=now_utc - timedelta(days=18), created_by=owner.id),
            BeamLoading(loom_id=looms[2].id, beam_id=b_103.id, loaded_at=now_utc - timedelta(days=15), created_by=owner.id),
            BeamLoading(loom_id=looms[3].id, beam_id=b_104.id, loaded_at=now_utc - timedelta(days=12), created_by=owner.id),
            BeamLoading(
                loom_id=looms[2].id,
                beam_id=b_100.id,
                loaded_at=now_utc - timedelta(days=39),
                unloaded_at=now_utc - timedelta(days=30),
                unload_reason="COMPLETED",
                created_by=owner.id,
            ),
        ])

        # Weft receipts across all active beams + BM-100 (35 kg used for 400 m vs expected 28.8 kg -> wastage alert!)
        db.add_all([
            WeftReceipt(beam_id=b_101.id, trader_id=t_murugan.id, sort_id=s_gada.id, received_date=today - timedelta(days=8), bags=1, net_weight_kg=Decimal("40.000"), created_by=owner.id),
            WeftReceipt(beam_id=b_102.id, trader_id=t_murugan.id, sort_id=s_gada.id, received_date=today - timedelta(days=7), bags=1, net_weight_kg=Decimal("42.000"), created_by=owner.id),
            WeftReceipt(beam_id=b_103.id, trader_id=t_kaveri.id, sort_id=s_poplin.id, received_date=today - timedelta(days=6), bags=1, net_weight_kg=Decimal("36.000"), created_by=owner.id),
            WeftReceipt(beam_id=b_104.id, trader_id=t_kaveri.id, sort_id=s_poplin.id, received_date=today - timedelta(days=5), bags=1, net_weight_kg=Decimal("38.000"), created_by=owner.id),
            WeftReceipt(beam_id=b_100.id, trader_id=t_kaveri.id, sort_id=s_poplin.id, received_date=today - timedelta(days=38), bags=1, net_weight_kg=Decimal("40.000"), created_by=owner.id),
        ])

        # 35 days of Shuttle shifts (< 30m/shift) with counter readings across ALL 5 looms (S-01..S-05)
        # Attach BM-101..104 only to recent 10 days (19 shifts) so active beams show realistic ~390-463m remaining!
        # Today logs Shift 1 (125.00 m total); Shift 2 stays open for live testing!
        loom_profiles = [
            (looms[0], w_arumugam, b_101.id, Decimal("28.00"), Decimal("1000.00")),
            (looms[1], w_ramesh, b_102.id, Decimal("26.00"), Decimal("1200.00")),
            (looms[2], w_arumugam, b_103.id, Decimal("24.00"), Decimal("800.00")),
            (looms[3], w_ramesh, b_104.id, Decimal("25.00"), Decimal("950.00")),
            (looms[4], w_arumugam, None, Decimal("22.00"), Decimal("600.00")),
        ]
        counters = [p[4] for p in loom_profiles]

        for day_off in range(34, -1, -1):
            d = today - timedelta(days=day_off)
            shifts_today = (1,) if day_off == 0 else (1, 2)
            for s_no in shifts_today:
                for l_idx, (loom_obj, weaver_obj, b_id, metres_each, _) in enumerate(loom_profiles):
                    is_stopped_shift = l_idx == 4 and day_off == 2 and s_no == 2
                    m_woven = Decimal("0.00") if is_stopped_shift else metres_each
                    dt_mins = 600 if is_stopped_shift else 0
                    start_m = counters[l_idx]
                    end_m = start_m + m_woven
                    counters[l_idx] = end_m
                    db.add(
                        ShiftEntry(
                            client_uuid=f"demo-s{l_idx+1:02d}-{d.isoformat()}-{s_no}",
                            loom_id=loom_obj.id,
                            weaver_id=weaver_obj.id,
                            beam_id=b_id if day_off <= 9 else None,
                            entry_date=d,
                            shift_no=s_no,
                            entry_mode="DIRECT",
                            start_meter=start_m,
                            end_meter=end_m,
                            net_metres=m_woven,
                            planned_mins=600,
                            power_cut_mins=0,
                            downtime_mins=dt_mins,
                            defective_metres=Decimal("0.00"),
                            created_by=sup.id,
                        )
                    )

        # Historical completed BM-100 woven metres (400m on S-03 before BM-103)
        db.add(
            ShiftEntry(
                client_uuid="demo-bm100-hist",
                loom_id=looms[2].id,
                weaver_id=w_arumugam.id,
                beam_id=b_100.id,
                entry_date=today - timedelta(days=36),
                shift_no=1,
                entry_mode="DIRECT",
                net_metres=Decimal("400.00"),
                planned_mins=600,
                power_cut_mins=0,
                downtime_mins=0,
                defective_metres=Decimal("0.00"),
                created_by=owner.id,
            )
        )

        # Attendance for Meena Pirn Winder (last 6 days = 6 PRESENT shifts) & next Sunday holiday
        for day_off in range(6, 0, -1):
            db.add(
                WeaverAttendance(
                    weaver_id=w_meena.id,
                    attendance_date=today - timedelta(days=day_off),
                    shift_no=1,
                    status="PRESENT",
                    created_by=sup.id,
                )
            )
        db.add(
            ShedCalendar(
                calendar_date=today + timedelta(days=(6 - today.weekday()) % 7 or 7),
                is_working_day=False,
                planned_shifts=0,
                note="Weekly Shed Off (Demo)",
                created_by=owner.id,
            )
        )

        # Advance (₹500 to Arumugam), plus 1 historical finalized Payslip for Lakshmi (current week)
        db.add(
            Advance(
                weaver_id=w_arumugam.id,
                advance_date=today - timedelta(days=2),
                amount_paise=50000,
                note="Demo mid-week advance (Uthaav)",
                created_by=owner.id,
            )
        )
        db.add(
            Payslip(
                weaver_id=w_lakshmi.id,
                period_start=today - timedelta(days=6),
                period_end=today,
                wage_mode_snapshot="FIXED_WEEKLY",
                units_worked=Decimal("1.00"),
                rate_paise_snapshot=250000,
                gross_paise=250000,
                advance_deducted_paise=0,
                defect_deduction_paise=0,
                net_payable_paise=250000,
                status="FINALIZED",
                created_by=owner.id,
            )
        )

        # Deliveries: past-month challans + current-week challans (weekly vs monthly clearly distinct!)
        d_prev1 = Delivery(trader_id=t_murugan.id, challan_no="CH-198", delivery_date=today - timedelta(days=22), total_metres=Decimal("3200.00"), source="MANUAL", created_by=owner.id)
        d_prev2 = Delivery(trader_id=t_kaveri.id, challan_no="CH-199", delivery_date=today - timedelta(days=14), total_metres=Decimal("2500.00"), source="MANUAL", created_by=owner.id)
        d1 = Delivery(trader_id=t_murugan.id, challan_no="CH-201", delivery_date=today - timedelta(days=3), total_metres=Decimal("1500.00"), source="MANUAL", created_by=owner.id)
        d2 = Delivery(trader_id=t_murugan.id, challan_no="CH-202", delivery_date=today - timedelta(days=1), total_metres=Decimal("1000.00"), source="MANUAL", created_by=owner.id)
        db.add_all([d_prev1, d_prev2, d1, d2])
        db.flush()
        db.add_all([
            DeliveryItem(delivery_id=d_prev1.id, beam_id=b_101.id, sort_id=s_gada.id, pieces=32, metres=Decimal("3200.00"), applied_rate_paise=600, created_by=owner.id),
            DeliveryItem(delivery_id=d_prev2.id, beam_id=b_103.id, sort_id=s_poplin.id, pieces=25, metres=Decimal("2500.00"), applied_rate_paise=550, created_by=owner.id),
            DeliveryItem(delivery_id=d1.id, beam_id=b_101.id, sort_id=s_gada.id, pieces=15, metres=Decimal("1500.00"), applied_rate_paise=600, created_by=owner.id),
            DeliveryItem(delivery_id=d2.id, beam_id=b_102.id, sort_id=s_gada.id, pieces=10, metres=Decimal("1000.00"), applied_rate_paise=550, created_by=owner.id),
        ])

        # Payments & Expenses across weekly & monthly windows
        db.add_all([
            TraderPayment(
                trader_id=t_murugan.id,
                payment_date=today - timedelta(days=18),
                amount_paise=1920000,
                shortage_deduction_paise=0,
                reference="NEFT-PREV-198",
                created_by=owner.id,
            ),
            TraderPayment(
                trader_id=t_kaveri.id,
                payment_date=today - timedelta(days=10),
                amount_paise=1375000,
                shortage_deduction_paise=0,
                reference="NEFT-PREV-199",
                created_by=owner.id,
            ),
            TraderPayment(
                trader_id=t_murugan.id,
                payment_date=today - timedelta(days=1),
                amount_paise=800000,
                shortage_deduction_paise=20000,
                reference="UPI-DEMO-01",
                created_by=owner.id,
            ),
        ])
        db.add_all([
            Expense(expense_date=today - timedelta(days=18), category="Maintenance", amount_paise=140000, note="Reed cleaning & motor belt", created_by=owner.id),
            Expense(expense_date=today - timedelta(days=4), category="Spares & Shuttles", amount_paise=120000, note="4 pickers + shuttle pins", created_by=owner.id),
            Expense(expense_date=today - timedelta(days=2), category="Loom Oil", amount_paise=80000, note="Machine lubrication oil", created_by=owner.id),
        ])

        # 5 Bi-Monthly EB Bills anchored relative to today so latest cycle appears in Weekly & Monthly Summary
        eb_samples = [
            (today - timedelta(days=301), today - timedelta(days=242), Decimal("2480"), 965000, 90, "P1 Summer"),
            (today - timedelta(days=241), today - timedelta(days=182), Decimal("2190"), 782000, 60, "P2 Normal"),
            (today - timedelta(days=181), today - timedelta(days=122), Decimal("1420"), 345000, 30, "P3 Festival"),
            (today - timedelta(days=121), today - timedelta(days=62), Decimal("1980"), 642000, 45, "P4 Steady"),
            (today - timedelta(days=61), today - timedelta(days=1), Decimal("2150"), 756000, 30, "P5 Current Bill"),
        ]
        for ps, pe, u, net_p, pc_m, note in eb_samples:
            en_p = calculate_energy_charge_paise(u, tariff)
            db.add(
                EbBill(
                    tariff_plan_id=tariff.id,
                    period_start=ps,
                    period_end=pe,
                    units_consumed=u,
                    energy_paise=en_p,
                    overhead_paise=max(0, net_p - en_p),
                    net_bill_paise=net_p,
                    total_power_cut_mins=pc_m,
                    notes=note,
                    created_by=owner.id,
                )
            )
        db.add(EbReading(reading_date=today - timedelta(days=2), kwh_total=Decimal("15420.50"), note="Bi-monthly close check", created_by=owner.id))

        # Open realistic Alerts (Rate Cut + Weft Wastage)
        db.add_all([
            Alert(
                alert_type="RATE_UNDERPAYMENT",
                severity="CRITICAL",
                message="Challan CH-202 (Murugan Textiles): paid ₹5.50/m below agreed ₹6.00/m. Shortfall = ₹500.00.",
                status="OPEN",
            ),
            Alert(
                alert_type="WEFT_WASTAGE",
                loom_id=looms[2].id,
                severity="WARN",
                message="Beam BM-100: weft wastage 21.53% exceeds sort limit 3.0% (consumed 35.000 kg vs expected 28.800 kg).",
                status="OPEN",
            ),
        ])

        # Seed 2 sample cloth inspections (1 CONFIRMED_DEFECT + 1 CONFIRMED_CLEAN) without adding shift defects yet
        if MODEL_PATH.exists() and MODEL_CARD_PATH.exists():
            card = load_model_card()
            samples = card.get("samples", [])
            defect_s = next((s for s in samples if s.get("is_defect")), None)
            clean_s = next((s for s in samples if not s.get("is_defect")), None)
            demo_samples = [
                (defect_s, "CONFIRMED_DEFECT", defect_s["ground_truth_label"] if defect_s else "Broken End", looms[0].id, b_101.id, w_arumugam.id),
                (clean_s, "CONFIRMED_CLEAN", "Clean Cloth", looms[1].id, b_102.id, w_ramesh.id),
            ]
            for s_meta, r_status, r_label, l_id, b_id, w_id in demo_samples:
                if not s_meta:
                    continue
                s_path = SAMPLES_DIR / s_meta["filename"]
                if not s_path.exists():
                    continue
                pred_res = analyze_cloth_image_bytes(s_path.read_bytes())
                insp_row = Inspection(
                    loom_id=l_id,
                    beam_id=b_id,
                    weaver_id=w_id,
                    image_path=pred_res["raw_filename"],
                    heatmap_path=pred_res["heatmap_filename"],
                    review_status=r_status,
                    reviewed_label=r_label,
                    defective_metres=Decimal("0.00"),
                    is_reference_sample=True,
                    inspected_at=now_utc - timedelta(hours=3),
                    created_by=sup.id,
                )
                db.add(insp_row)
                db.flush()
                db.add(
                    DefectPrediction(
                        inspection_id=insp_row.id,
                        model_version=pred_res["model_version"],
                        predicted_label=pred_res["predicted_label"],
                        confidence=Decimal(str(pred_res["confidence"])),
                        threshold_used=Decimal(str(pred_res["threshold_used"])),
                        is_uncertain=pred_res["is_uncertain"],
                        inference_ms=Decimal(str(pred_res["inference_ms"])),
                    )
                )

        record_audit(
            db,
            entity_type="demo_seed",
            entity_id=1,
            action="CREATE",
            changed_by=owner.id,
            new_values={"db": db_path.name, "looms": 5},
            reason="Seeded isolated 5-loom demo dataset",
        )
        db.commit()

    engine.dispose()
    return {"db_path": str(db_path), "looms": 5, "owner_username": "welcome123", "supervisor_username": "welcome@123"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe isolated LOOMOS demo database tool.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="Reset and seed loomos_demo.db with 5-loom shuttle demo data.")
    mode.add_argument("--clean", action="store_true", help="Reset ONLY loomos_demo.db to blank empty setup state.")
    mode.add_argument(
        "--reset-production-db",
        action="store_true",
        help="Reset production loomos.db (requires interactive typed confirmation + automatic backup).",
    )
    parser.add_argument("--db", type=Path, default=DEMO_DB_PATH, help="Target demo DB path (default: data/loomos_demo.db).")
    args = parser.parse_args()

    target = args.db.resolve()
    if (args.demo or args.clean) and target == REAL_DB_PATH:
        print("REFUSING to modify production loomos.db! --demo and --clean strictly target loomos_demo.db.", file=sys.stderr)
        sys.exit(2)

    if args.demo:
        res = populate_demo_shed(target)
        print(f"[DEMO SEEDED] {res['db_path']} | Owner: welcome123 / welcome123 | Supervisor: welcome@123 / welcome@123")
    elif args.clean:
        _reset_sqlite_file(target)
        print(f"[DEMO CLEAN RESET] {target} reset to empty uninitialized schema (setup wizard ready). Real loomos.db untouched.")
    elif args.reset_production_db:
        confirm = input("WARNING: Type RESET_REAL_LOOMOS_DB to backup & reset production loomos.db: ").strip()
        if confirm != "RESET_REAL_LOOMOS_DB":
            print("Aborted cleanly. Real loomos.db was not modified.")
            sys.exit(1)
        bak = _backup_before_prod_reset()
        print(f"[BACKUP CREATED] {bak}")
        _reset_sqlite_file(REAL_DB_PATH)
        print(f"[PRODUCTION RESET] {REAL_DB_PATH} reset to empty schema after backup.")


if __name__ == "__main__":
    main()
