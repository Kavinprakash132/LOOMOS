"""Pydantic schemas for Step 3 / Phase 2 Cloth Vision Inspection & Reconciled Model Card."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelComparisonEntry(BaseModel):
    name: str
    arch: str
    threshold: float
    defect_recall: float
    defect_f1: float
    defect_precision: float
    macro_f1: float
    roc_auc: float
    overall_accuracy_pct: float
    inference_ms: float
    train_seconds: float
    confusion_matrix: list[list[int]]


class HeldOutSplitSummary(BaseModel):
    train_strips: int
    val_strips: int
    test_strips: int
    train_defect_strips: int
    train_clean_strips: int
    val_defect_strips: int
    val_clean_strips: int
    test_defect_strips: int
    test_clean_strips: int
    test_total_patches: int
    test_defect_patches: int
    test_clean_patches: int
    imbalance_note: str


class ReferenceSampleInfo(BaseModel):
    id: str
    title: str
    defect_code: str
    ground_truth_label: str
    is_defect: bool
    filename: str
    image_url: str


class ModelCardResponse(BaseModel):
    winning_model_name: str
    model_version: str
    architecture: str
    threshold: float
    held_out_split_summary: HeldOutSplitSummary
    comparison: list[ModelComparisonEntry]
    samples: list[ReferenceSampleInfo]


class DefectPredictionInfo(BaseModel):
    model_version: str
    predicted_label: str
    confidence: float
    threshold_used: float
    is_uncertain: bool
    inference_ms: float


class InspectionRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    loom_id: int | None
    loom_number: str | None = None
    beam_id: int | None
    beam_no: str | None = None
    weaver_id: int | None
    weaver_name: str | None = None
    shift_entry_id: int | None
    raw_image_url: str
    heatmap_image_url: str | None = None
    review_status: Literal["PENDING", "CONFIRMED_DEFECT", "CONFIRMED_CLEAN"]
    reviewed_label: str | None
    defective_metres: Decimal
    is_reference_sample: bool
    inspected_at: datetime
    prediction: DefectPredictionInfo | None = None


class InspectionReviewRequest(BaseModel):
    review_status: Literal["CONFIRMED_DEFECT", "CONFIRMED_CLEAN"]
    reviewed_label: str = Field(min_length=1, max_length=50)
    defective_metres: Decimal = Field(default=Decimal("0.00"), ge=0)
    loom_id: int | None = None
    beam_id: int | None = None
    weaver_id: int | None = None
    add_to_today_shift: bool = False
