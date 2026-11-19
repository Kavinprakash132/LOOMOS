"""CPU ONNX runtime inference & spatial CAM heatmap generation for LOOMOS Cloth Inspection."""

from __future__ import annotations

import json
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

from app.core.config import DATA_DIR, get_settings

VISION_DIR = DATA_DIR / "vision"
SAMPLES_DIR = VISION_DIR / "samples"
MODEL_PATH = VISION_DIR / "winning_model.onnx"
MODEL_CARD_PATH = VISION_DIR / "model_card.json"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@lru_cache
def load_model_card() -> dict[str, Any]:
    """Load reconciled AITEX model card JSON from backend/data/vision/model_card.json."""
    if not MODEL_CARD_PATH.exists():
        raise RuntimeError(f"Vision model_card.json not found at {MODEL_CARD_PATH}")
    return json.loads(MODEL_CARD_PATH.read_text(encoding="utf-8"))


@lru_cache
def _get_onnx_session() -> ort.InferenceSession:
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Vision ONNX model not found at {MODEL_PATH}")
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    return ort.InferenceSession(str(MODEL_PATH), sess_options=opts, providers=["CPUExecutionProvider"])


def get_inspections_storage_dir() -> Path:
    """Return filesystem directory where inspection raw + heatmap PNGs are stored."""
    target = get_settings().upload_dir / "inspections"
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_sample_metadata(sample_id: str) -> dict[str, Any] | None:
    card = load_model_card()
    for s in card.get("samples", []):
        if s.get("id") == sample_id:
            return s
    return None


def _prepare_display_and_tensor(image_bytes: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Decode photo/patch -> square 256x256 RGB display array and CLAHE-normalized [1,3,224,224] tensor."""
    with Image.open(Path_or_BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        w, h = im.size
        if w != h:
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            im = im.crop((left, top, left + side, top + side))
        disp_rgb = np.array(im.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.uint8)

    gray = cv2.cvtColor(disp_rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    eq_rgb = np.stack([eq, eq, eq], axis=-1)
    resized = cv2.resize(eq_rgb, (224, 224), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    norm = (resized - IMAGENET_MEAN) / IMAGENET_STD
    tensor = np.transpose(norm, (2, 0, 1))[None, ...].astype(np.float32)
    return disp_rgb, tensor


def Path_or_BytesIO(data: bytes):
    import io

    return io.BytesIO(data)


def _render_cam_overlay(disp_rgb: np.ndarray, conv_maps: np.ndarray, cam_weights: list[float]) -> np.ndarray:
    """Compute ReLU class-activation overlay from [1, C, H, W] feature maps onto 256x256 cloth RGB."""
    fmap = conv_maps[0]  # [C, 7, 7]
    w_arr = np.array(cam_weights, dtype=np.float32)
    if w_arr.shape[0] != fmap.shape[0]:
        cam = np.mean(np.maximum(fmap, 0.0), axis=0)
    else:
        cam = np.tensordot(w_arr, fmap, axes=(0, 0))
        cam = np.maximum(cam, 0.0)

    cmax = float(cam.max())
    if cmax > 1e-6:
        cam = cam / cmax
    cam_up = cv2.resize(cam.astype(np.float32), (256, 256), interpolation=cv2.INTER_CUBIC)
    cam_up = np.clip(cam_up, 0.0, 1.0)

    heat_u8 = np.uint8(255 * cam_up)
    heat_bgr = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)

    alpha = np.where(cam_up > 0.25, 0.15 + 0.45 * cam_up, 0.08)[..., None]
    blended = disp_rgb.astype(np.float32) * (1.0 - alpha) + heat_rgb * alpha
    return np.clip(blended, 0, 255).astype(np.uint8)


def analyze_cloth_image_bytes(image_bytes: bytes) -> dict[str, Any]:
    """Run ONNX Two-Output inference + Grad-CAM overlay and persist PNGs to inspection storage."""
    card = load_model_card()
    session = _get_onnx_session()

    disp_rgb, tensor = _prepare_display_and_tensor(image_bytes)
    t0 = time.perf_counter()
    logits, conv_maps = session.run(["logits", "conv_maps"], {"image": tensor})
    inference_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    row_logits = logits[0].astype(np.float64)
    row_logits = row_logits - np.max(row_logits)
    exps = np.exp(row_logits)
    probs = exps / np.sum(exps)
    defect_prob = float(probs[1])

    threshold = float(card["threshold"])
    is_defect = defect_prob >= threshold
    predicted_label = "Defect Flagged" if is_defect else "Clean Cloth"
    is_uncertain = abs(defect_prob - threshold) <= 0.08

    overlay_rgb = _render_cam_overlay(disp_rgb, conv_maps, card.get("cam_weights", []))

    storage_dir = get_inspections_storage_dir()
    uid = uuid.uuid4().hex[:12]
    raw_fname = f"insp_{uid}_raw.png"
    heat_fname = f"insp_{uid}_cam.png"

    Image.fromarray(disp_rgb).save(storage_dir / raw_fname, format="PNG")
    Image.fromarray(overlay_rgb).save(storage_dir / heat_fname, format="PNG")

    return {
        "raw_filename": raw_fname,
        "heatmap_filename": heat_fname,
        "model_version": card["model_version"],
        "predicted_label": predicted_label,
        "confidence": round(defect_prob, 4),
        "threshold_used": round(threshold, 4),
        "is_uncertain": bool(is_uncertain),
        "inference_ms": inference_ms,
    }
