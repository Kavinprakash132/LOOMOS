"""CPU ONNX runtime inference & Multi-Scale Stitched Spatial CAM heatmap generation for LOOMOS Cloth Inspection."""

from __future__ import annotations

import io
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

# Guard against PNG/TIFF decompression bombs exhausting RAM on small servers
Image.MAX_IMAGE_PIXELS = 40_000_000

VISION_DIR = DATA_DIR / "vision"
SAMPLES_DIR = VISION_DIR / "samples"
MODEL_PATH = VISION_DIR / "winning_model.onnx"
MODEL_CARD_PATH = VISION_DIR / "model_card.json"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@lru_cache
def load_model_card() -> dict[str, Any]:
    """Load vision model card JSON from backend/data/vision/model_card.json."""
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


def _rgb_array_to_tensor(rgb: np.ndarray) -> np.ndarray:
    resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    norm = (resized - IMAGENET_MEAN) / IMAGENET_STD
    return np.transpose(norm, (2, 0, 1)).astype(np.float32)


def _prepare_legacy_clahe(im: Image.Image) -> tuple[np.ndarray, np.ndarray, list[tuple[float, float, float, float]]]:
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
    tensor = _rgb_array_to_tensor(eq_rgb)[None, ...]
    return disp_rgb, tensor, [(0.0, 0.0, 1.0, 1.0)]


def _prepare_rgb_multiscale(im: Image.Image) -> tuple[np.ndarray, np.ndarray, list[tuple[float, float, float, float]]]:
    """Decode photo -> square display RGB (up to 384x384) + single or 5-view multi-scale RGB batch."""
    w, h = im.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        im = im.crop((left, top, left + side, top + side))

    side = im.size[0]
    disp_side = 384 if side >= 320 else 256
    disp_rgb = np.array(im.resize((disp_side, disp_side), Image.Resampling.BILINEAR), dtype=np.uint8)

    # Full-resolution source array for high-detail tiling on phone camera / gallery photos
    src_side = min(side, 768)
    src_rgb = np.array(im.resize((src_side, src_side), Image.Resampling.BILINEAR), dtype=np.uint8)

    if side <= 320:
        return disp_rgb, _rgb_array_to_tensor(src_rgb)[None, ...], [(0.0, 0.0, 1.0, 1.0)]

    # 5-view multi-scale tiling: full frame + 4 overlapping 60% quadrants catches tiny holes/threads anywhere
    boxes: list[tuple[float, float, float, float]] = [
        (0.0, 0.0, 1.0, 1.0),
        (0.0, 0.0, 0.60, 0.60),
        (0.40, 0.0, 1.0, 0.60),
        (0.0, 0.40, 0.60, 1.0),
        (0.40, 0.40, 1.0, 1.0),
    ]
    tensors: list[np.ndarray] = []
    for x0f, y0f, x1f, y1f in boxes:
        x0, y0 = int(round(x0f * src_side)), int(round(y0f * src_side))
        x1, y1 = int(round(x1f * src_side)), int(round(y1f * src_side))
        crop = src_rgb[y0:y1, x0:x1]
        tensors.append(_rgb_array_to_tensor(crop))

    batch = np.stack(tensors, axis=0).astype(np.float32)
    return disp_rgb, batch, boxes


def _prepare_display_and_tensor(image_bytes: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Single-view helper used by RQ3 few-shot embedding extraction."""
    card = load_model_card()
    with Image.open(io.BytesIO(image_bytes)) as raw_im:
        im = ImageOps.exif_transpose(raw_im).convert("RGB")
    if card.get("preprocess", "legacy_clahe") == "rgb_multiscale":
        w, h = im.size
        if w != h:
            side = min(w, h)
            im = im.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
        disp_rgb = np.array(im.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.uint8)
        return disp_rgb, _rgb_array_to_tensor(disp_rgb)[None, ...]
    disp_rgb, tensor, _ = _prepare_legacy_clahe(im)
    return disp_rgb, tensor


def _single_cam_map(fmap: np.ndarray, w_arr: np.ndarray) -> np.ndarray:
    if w_arr.shape[0] != fmap.shape[0]:
        cam = np.mean(np.maximum(fmap, 0.0), axis=0)
    else:
        cam = np.tensordot(w_arr, fmap, axes=(0, 0))
        cam = np.maximum(cam, 0.0)
    cmax = float(cam.max())
    if cmax > 1e-6:
        cam = cam / cmax
    return cam.astype(np.float32)


def _tile_feather_mask(h: int, w: int, x0f: float, y0f: float, x1f: float, y1f: float) -> np.ndarray:
    """Create a smooth cosine-feathered 2D mask that tapers ONLY on interior tile seams (never outer edges)."""
    wy = np.ones(h, dtype=np.float32)
    wx = np.ones(w, dtype=np.float32)
    fy = max(4, int(round(h * 0.22)))
    fx = max(4, int(round(w * 0.22)))
    ramp_y = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fy, dtype=np.float32)))
    ramp_x = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, fx, dtype=np.float32)))
    if y0f > 0.0:
        wy[:fy] = np.minimum(wy[:fy], ramp_y)
    if y1f < 1.0:
        wy[-fy:] = np.minimum(wy[-fy:], ramp_y[::-1])
    if x0f > 0.0:
        wx[:fx] = np.minimum(wx[:fx], ramp_x)
    if x1f < 1.0:
        wx[-fx:] = np.minimum(wx[-fx:], ramp_x[::-1])
    return np.outer(wy, wx)


def _render_multiscale_cam_overlay(
    disp_rgb: np.ndarray,
    conv_maps: np.ndarray,
    view_probs: np.ndarray,
    boxes: list[tuple[float, float, float, float]],
    cam_weights: list[float],
) -> np.ndarray:
    """Stitch full-frame + localized tile CAMs with feathered blending so zero hard seams appear."""
    H, W = disp_rgb.shape[:2]
    w_arr = np.array(cam_weights, dtype=np.float32)

    accum = np.zeros((H, W), dtype=np.float32)
    weight_sum = np.zeros((H, W), dtype=np.float32)

    for idx, (x0f, y0f, x1f, y1f) in enumerate(boxes):
        cam_small = _single_cam_map(conv_maps[idx], w_arr)
        x0, y0 = int(round(x0f * W)), int(round(y0f * H))
        x1, y1 = max(x0 + 1, int(round(x1f * W))), max(y0 + 1, int(round(y1f * H)))
        th, tw = y1 - y0, x1 - x0
        cam_up = cv2.resize(cam_small, (tw, th), interpolation=cv2.INTER_CUBIC)
        cam_up = np.clip(cam_up, 0.0, 1.0)
        # Weight high-defect tiles stronger and feather interior seam edges smoothly
        v_weight = 0.25 + float(view_probs[idx]) ** 2
        if idx == 0 and len(boxes) > 1:
            v_weight *= 0.65
            spatial_w = np.full((th, tw), v_weight, dtype=np.float32)
        else:
            spatial_w = _tile_feather_mask(th, tw, x0f, y0f, x1f, y1f) * v_weight
        accum[y0:y1, x0:x1] += cam_up * spatial_w
        weight_sum[y0:y1, x0:x1] += spatial_w

    stitched = accum / np.maximum(weight_sum, 1e-6)
    stitched = cv2.GaussianBlur(stitched, (0, 0), sigmaX=max(2.5, W * 0.014))
    smax = float(stitched.max())
    if smax > 1e-6:
        stitched = stitched / smax
    stitched = np.clip(stitched, 0.0, 1.0)

    heat_u8 = np.uint8(255 * stitched)
    heat_bgr = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)

    alpha = np.where(stitched > 0.28, 0.14 + 0.48 * stitched, 0.06)[..., None]
    blended = disp_rgb.astype(np.float32) * (1.0 - alpha) + heat_rgb * alpha
    return np.clip(blended, 0, 255).astype(np.uint8)


def analyze_cloth_image_bytes(image_bytes: bytes) -> dict[str, Any]:
    """Run ONNX Two-Output inference + Multi-Scale Stitched Grad-CAM overlay and persist PNGs."""
    card = load_model_card()
    session = _get_onnx_session()

    with Image.open(io.BytesIO(image_bytes)) as raw_im:
        im = ImageOps.exif_transpose(raw_im).convert("RGB")

    preprocess = card.get("preprocess", "legacy_clahe")
    if preprocess == "rgb_multiscale":
        disp_rgb, batch_tensor, boxes = _prepare_rgb_multiscale(im)
    else:
        disp_rgb, batch_tensor, boxes = _prepare_legacy_clahe(im)

    t0 = time.perf_counter()
    logits, conv_maps = session.run(["logits", "conv_maps"], {"image": batch_tensor})
    inference_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    # Numerically stable softmax across batch
    shifted = logits.astype(np.float64) - np.max(logits.astype(np.float64), axis=1, keepdims=True)
    exps = np.exp(shifted)
    probs = exps / np.sum(exps, axis=1, keepdims=True)
    view_probs = probs[:, 1].astype(np.float32)

    if len(view_probs) == 1:
        defect_prob = float(view_probs[0])
    else:
        p_full = float(view_probs[0])
        p_tile_max = float(np.max(view_probs[1:]))
        defect_prob = float(max(p_full, 0.94 * p_tile_max))

    threshold = float(card["threshold"])
    is_defect = defect_prob >= threshold
    predicted_label = "Defect Flagged" if is_defect else "Clean Cloth"
    is_uncertain = abs(defect_prob - threshold) <= 0.08

    overlay_rgb = _render_multiscale_cam_overlay(disp_rgb, conv_maps, view_probs, boxes, card.get("cam_weights", []))

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
