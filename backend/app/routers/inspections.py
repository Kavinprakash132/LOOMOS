"""API endpoints for Phase 2 Cloth Vision Inspection (/inspect), Grad-CAM overlays, and Model Card."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.core import Beam, DefectPrediction, Inspection, Loom, ShiftEntry, User, Weaver
from app.schemas.step3 import (
    DefectPredictionInfo,
    InspectionRecordResponse,
    InspectionReviewRequest,
    ModelCardResponse,
    ReferenceSampleInfo,
)
from app.services.vision_service import (
    SAMPLES_DIR,
    analyze_cloth_image_bytes,
    get_inspections_storage_dir,
    get_sample_metadata,
    load_model_card,
)

router = APIRouter(prefix="/api/v1/inspections", tags=["inspections"])


def _serialize_inspection(
    db: Session,
    insp: Inspection,
    pred: DefectPrediction | None = None,
) -> InspectionRecordResponse:
    loom = db.get(Loom, insp.loom_id) if insp.loom_id else None
    beam = db.get(Beam, insp.beam_id) if insp.beam_id else None
    weaver = db.get(Weaver, insp.weaver_id) if insp.weaver_id else None

    if pred is None:
        pred = db.scalar(
            select(DefectPrediction)
            .where(DefectPrediction.inspection_id == insp.id)
            .order_by(DefectPrediction.id.desc())
            .limit(1)
        )

    pred_info = (
        DefectPredictionInfo(
            model_version=pred.model_version,
            predicted_label=pred.predicted_label,
            confidence=float(pred.confidence),
            threshold_used=float(pred.threshold_used or 0.5),
            is_uncertain=pred.is_uncertain,
            inference_ms=float(pred.inference_ms),
        )
        if pred
        else None
    )

    return InspectionRecordResponse(
        id=insp.id,
        loom_id=insp.loom_id,
        loom_number=loom.loom_number if loom else None,
        beam_id=insp.beam_id,
        beam_no=beam.beam_no if beam else None,
        weaver_id=insp.weaver_id,
        weaver_name=weaver.full_name if weaver else None,
        shift_entry_id=insp.shift_entry_id,
        raw_image_url=f"/api/v1/inspections/{insp.id}/image/raw",
        heatmap_image_url=f"/api/v1/inspections/{insp.id}/image/heatmap" if insp.heatmap_path else None,
        review_status=insp.review_status,  # type: ignore[arg-type]
        reviewed_label=insp.reviewed_label,
        defective_metres=insp.defective_metres,
        is_reference_sample=insp.is_reference_sample,
        inspected_at=insp.inspected_at,
        prediction=pred_info,
    )


@router.get("/model-card", response_model=ModelCardResponse)
def get_vision_model_card(
    _user: Annotated[User, Depends(get_current_user)],
) -> ModelCardResponse:
    """Return reconciled ResNet-18 vs MobileNetV3 metrics, split info, and 6 held-out AITEX samples."""
    card = load_model_card()
    samples = [
        ReferenceSampleInfo(
            **s,
            image_url=f"/api/v1/inspections/samples/{s['id']}/image",
        )
        for s in card.get("samples", [])
    ]
    return ModelCardResponse(
        winning_model_name=card["winning_model_name"],
        model_version=card["model_version"],
        architecture=card["architecture"],
        threshold=card["threshold"],
        held_out_split_summary=card["held_out_split_summary"],
        comparison=card["comparison"],
        samples=samples,
    )


@router.get("/samples/{sample_id}/image")
def get_reference_sample_image(sample_id: str) -> FileResponse:
    """Serve a held-out AITEX demo sample image."""
    sample = get_sample_metadata(sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference sample not found")
    path = SAMPLES_DIR / sample["filename"]
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference sample image missing on disk")
    return FileResponse(path, media_type="image/png")


@router.post("/analyze", response_model=InspectionRecordResponse, status_code=status.HTTP_201_CREATED)
async def analyze_fabric_photo(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile | None = File(default=None),
    sample_id: str | None = Form(default=None),
    loom_id: int | None = Form(default=None),
    beam_id: int | None = Form(default=None),
    weaver_id: int | None = Form(default=None),
) -> InspectionRecordResponse:
    """Run ONNX Two-Output inference + Grad-CAM overlay on uploaded cloth photo or held-out AITEX sample."""
    is_ref = False
    if file is not None:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded image file is empty")
    elif sample_id:
        sample = get_sample_metadata(sample_id)
        if not sample:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference sample not found")
        sample_path = SAMPLES_DIR / sample["filename"]
        if not sample_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference sample image missing")
        raw_bytes = sample_path.read_bytes()
        is_ref = True
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either a photo upload (file) or a demo sample_id",
        )

    if loom_id and not db.get(Loom, loom_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected loom not found")
    if beam_id and not db.get(Beam, beam_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected beam not found")
    if weaver_id and not db.get(Weaver, weaver_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected weaver not found")

    try:
        res = analyze_cloth_image_bytes(raw_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not decode or analyze cloth image: {exc}",
        ) from exc

    insp = Inspection(
        loom_id=loom_id,
        beam_id=beam_id,
        weaver_id=weaver_id,
        image_path=res["raw_filename"],
        heatmap_path=res["heatmap_filename"],
        review_status="PENDING",
        reviewed_label=None,
        defective_metres=Decimal("0.00"),
        is_reference_sample=is_ref,
        inspected_at=datetime.now(timezone.utc),
        created_by=user.id,
    )
    db.add(insp)
    db.flush()

    pred = DefectPrediction(
        inspection_id=insp.id,
        model_version=res["model_version"],
        predicted_label=res["predicted_label"],
        confidence=Decimal(str(res["confidence"])),
        threshold_used=Decimal(str(res["threshold_used"])),
        is_uncertain=res["is_uncertain"],
        inference_ms=Decimal(str(res["inference_ms"])),
    )
    db.add(pred)
    db.commit()
    db.refresh(insp)
    db.refresh(pred)
    return _serialize_inspection(db, insp, pred)


@router.post("/{inspection_id}/review", response_model=InspectionRecordResponse)
def review_inspection(
    inspection_id: int,
    payload: InspectionReviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InspectionRecordResponse:
    """Confirm photo as Clean or Defect (saving every reviewed photo) and optionally update shift defect metres."""
    insp = db.get(Inspection, inspection_id)
    if not insp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection record not found")

    if payload.loom_id is not None:
        insp.loom_id = payload.loom_id
    if payload.beam_id is not None:
        insp.beam_id = payload.beam_id
    if payload.weaver_id is not None:
        insp.weaver_id = payload.weaver_id

    insp.review_status = payload.review_status
    insp.reviewed_label = payload.reviewed_label.strip()
    insp.defective_metres = (
        payload.defective_metres if payload.review_status == "CONFIRMED_DEFECT" else Decimal("0.00")
    )

    if (
        payload.add_to_today_shift
        and payload.review_status == "CONFIRMED_DEFECT"
        and insp.defective_metres > Decimal("0.00")
        and insp.loom_id is not None
    ):
        today = date.today()
        shift_row = db.scalar(
            select(ShiftEntry)
            .where(
                ShiftEntry.loom_id == insp.loom_id,
                ShiftEntry.entry_date == today,
                ShiftEntry.is_deleted.is_(False),
            )
            .order_by(ShiftEntry.shift_no.desc(), ShiftEntry.id.desc())
            .limit(1)
        )
        if not shift_row:
            shift_row = db.scalar(
                select(ShiftEntry)
                .where(
                    ShiftEntry.loom_id == insp.loom_id,
                    ShiftEntry.is_deleted.is_(False),
                )
                .order_by(ShiftEntry.entry_date.desc(), ShiftEntry.shift_no.desc(), ShiftEntry.id.desc())
                .limit(1)
            )
        if shift_row:
            old_def = str(shift_row.defective_metres)
            shift_row.defective_metres = (shift_row.defective_metres or Decimal("0.00")) + insp.defective_metres
            insp.shift_entry_id = shift_row.id
            record_audit(
                db,
                entity_type="shift_entry",
                entity_id=shift_row.id,
                action="UPDATE",
                changed_by=user.id,
                old_values={"defective_metres": old_def},
                new_values={"defective_metres": str(shift_row.defective_metres)},
                reason=f"Confirmed defect on Photo Inspection #{insp.id} ({insp.reviewed_label})",
            )

    record_audit(
        db,
        entity_type="inspection",
        entity_id=insp.id,
        action="UPDATE",
        changed_by=user.id,
        new_values={
            "review_status": insp.review_status,
            "reviewed_label": insp.reviewed_label,
            "defective_metres": str(insp.defective_metres),
        },
        reason="Human inspection review saved",
    )
    db.commit()
    db.refresh(insp)
    return _serialize_inspection(db, insp)


@router.get("", response_model=list[InspectionRecordResponse])
def list_inspections(
    review_status: str | None = None,
    loom_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[InspectionRecordResponse]:
    """List recent fabric inspections ordered newest-first."""
    stmt = select(Inspection).order_by(Inspection.id.desc()).limit(limit)
    if review_status:
        stmt = stmt.where(Inspection.review_status == review_status)
    if loom_id:
        stmt = stmt.where(Inspection.loom_id == loom_id)
    rows = db.scalars(stmt).all()
    return [_serialize_inspection(db, r) for r in rows]


@router.get("/{inspection_id}/image/{kind}")
def get_inspection_image(
    inspection_id: int,
    kind: str,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    """Serve stored raw cloth image or Grad-CAM heatmap overlay PNG."""
    if kind not in {"raw", "heatmap"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kind must be 'raw' or 'heatmap'")
    insp = db.get(Inspection, inspection_id)
    if not insp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    fname = insp.image_path if kind == "raw" else insp.heatmap_path
    if not fname:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested image unavailable")
    path = get_inspections_storage_dir() / fname
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file missing on disk")
    return FileResponse(path, media_type="image/png")
