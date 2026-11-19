"""Train & compare ResNet-18 + CLAHE vs MobileNetV3-Small + CLAHE on leak-free AITEX split,
then export winning Two-Output (logits, conv_maps) ONNX model, model_card.json, and 6 held-out reference samples.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader, Dataset

SEED = 42
DEFAULT_AITEX_DIR = Path(
    r"C:\Users\praka\.gemini\antigravity\brain\dd8df6b2-d122-4817-8f8a-86e471411396\scratch\vision_gate\aitex_repo\data\aitex"
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
VISION_OUT_DIR = BACKEND_ROOT / "data" / "vision"
SAMPLES_DIR = VISION_OUT_DIR / "samples"

AITEX_CODE_NAMES: dict[str, str] = {
    "002": "Broken End",
    "006": "Broken Yarn",
    "010": "Broken Pick",
    "016": "Weft Curling",
    "019": "Fuzzyball",
    "022": "Cut Selvage",
    "023": "Crease",
    "025": "Warp Ball",
    "027": "Knots",
    "029": "Contamination",
    "030": "Weft Crack",
    "036": "Nep",
}


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_strips(base: Path) -> tuple[list[dict], list[dict]]:
    defect_dir = base / "Defect_images"
    mask_dir = base / "Mask_images"
    nodefect_dir = base / "NODefect_images"
    mask_files = {p.name for p in mask_dir.iterdir() if p.is_file()}

    defect_strips: list[dict] = []
    for p in sorted(defect_dir.iterdir()):
        if not p.name.endswith(".png"):
            continue
        stem = p.stem
        cand = [m for m in mask_files if m.startswith(stem)]
        if not cand:
            continue
        with Image.open(p) as im:
            gray = np.array(im.convert("L"))
        h, w = gray.shape
        m_comb = np.zeros((h, w), dtype=np.uint8)
        for c in cand:
            with Image.open(mask_dir / c) as mim:
                arr = np.array(mim.convert("L"))
                if arr.shape == m_comb.shape:
                    m_comb = np.maximum(m_comb, arr)
        if int((m_comb > 0).sum()) == 0:
            continue
        parts = stem.split("_")
        code = parts[1] if len(parts) >= 2 else "000"
        defect_strips.append({"id": stem, "code": code, "gray": gray, "mask": m_comb})

    clean_strips: list[dict] = []
    for fdir in sorted(nodefect_dir.iterdir()):
        if not fdir.is_dir():
            continue
        for p in sorted(fdir.iterdir()):
            if not p.name.endswith(".png"):
                continue
            with Image.open(p) as im:
                gray = np.array(im.convert("L"))
            clean_strips.append({"id": f"{fdir.name}/{p.name}", "weave": fdir.name, "gray": gray})
    return defect_strips, clean_strips


def split_list(items: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    n = len(items)
    return items[: int(0.70 * n)], items[int(0.70 * n) : int(0.85 * n)], items[int(0.85 * n) :]


def extract_patches(
    d_list: list[dict],
    c_list: list[dict],
    extra_train_defect_shifts: bool = False,
) -> tuple[list[dict], list[dict]]:
    pos: list[dict] = []
    neg: list[dict] = []
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    for s in d_list:
        g, m = s["gray"], s["mask"]
        h, w = g.shape
        for i in range(w // 256):
            x0 = i * 256
            mp = m[:, x0 : x0 + 256]
            nz = int((mp > 0).sum())
            raw_patch = g[:, x0 : x0 + 256]
            eq_patch = clahe.apply(raw_patch)
            rgb_clahe = Image.fromarray(np.stack([eq_patch, eq_patch, eq_patch], axis=-1))
            rgb_raw = Image.fromarray(np.stack([raw_patch, raw_patch, raw_patch], axis=-1))
            if nz >= 25:
                pos.append({
                    "img": rgb_clahe,
                    "raw": rgb_raw,
                    "label": 1,
                    "strip_id": s["id"],
                    "code": s["code"],
                    "defect_px": nz,
                })
            elif nz == 0:
                neg.append({
                    "img": rgb_clahe,
                    "raw": rgb_raw,
                    "label": 0,
                    "strip_id": s["id"],
                    "code": "clean",
                    "defect_px": 0,
                })
        if extra_train_defect_shifts:
            num_lbl, _, stats, centroids = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8))
            for cid in range(1, num_lbl):
                if stats[cid, cv2.CC_STAT_AREA] < 20:
                    continue
                cx = int(centroids[cid][0])
                for offset in (-48, 0, 48):
                    x0 = max(0, min(w - 256, cx - 128 + offset))
                    mp = m[:, x0 : x0 + 256]
                    nz = int((mp > 0).sum())
                    if nz >= 25:
                        raw_patch = g[:, x0 : x0 + 256]
                        eq_patch = clahe.apply(raw_patch)
                        rgb_clahe = Image.fromarray(np.stack([eq_patch, eq_patch, eq_patch], axis=-1))
                        rgb_raw = Image.fromarray(np.stack([raw_patch, raw_patch, raw_patch], axis=-1))
                        pos.append({
                            "img": rgb_clahe,
                            "raw": rgb_raw,
                            "label": 1,
                            "strip_id": s["id"],
                            "code": s["code"],
                            "defect_px": nz,
                        })

    for s in c_list:
        g = s["gray"]
        h, w = g.shape
        for i in range(w // 256):
            raw_patch = g[:, i * 256 : (i + 1) * 256]
            eq_patch = clahe.apply(raw_patch)
            rgb_clahe = Image.fromarray(np.stack([eq_patch, eq_patch, eq_patch], axis=-1))
            rgb_raw = Image.fromarray(np.stack([raw_patch, raw_patch, raw_patch], axis=-1))
            neg.append({
                "img": rgb_clahe,
                "raw": rgb_raw,
                "label": 0,
                "strip_id": s["id"],
                "code": "clean",
                "defect_px": 0,
            })

    return pos, neg


class MemDataset(Dataset):
    def __init__(self, items: list[dict], tf: T.Compose) -> None:
        self.items = items
        self.tf = tf

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int):
        return self.tf(self.items[i]["img"]), self.items[i]["label"]


def get_probs(model: nn.Module, loader: DataLoader) -> tuple[np.ndarray, np.ndarray, float]:
    model.eval()
    probs, labels = [], []
    t0 = time.perf_counter()
    with torch.no_grad():
        for xb, yb in loader:
            p = torch.softmax(model(xb), dim=1)[:, 1]
            probs.extend(p.numpy().tolist())
            labels.extend(yb.numpy().tolist())
    ms = (time.perf_counter() - t0) * 1000.0 / max(len(labels), 1)
    return np.array(probs), np.array(labels), ms


def best_threshold(probs: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    best_t, best_f1 = 0.5, -1.0
    for t in np.linspace(0.30, 0.90, 25):
        f = float(f1_score(labels, (probs >= t).astype(int), zero_division=0))
        if f > best_f1:
            best_f1, best_t = f, float(t)
    return best_t, best_f1


def train_and_eval(
    name: str,
    arch: str,
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    pos_count: int,
    total_train: int,
    epochs: int,
    lr: float,
) -> tuple[nn.Module, dict]:
    pos_w = (total_train - pos_count) / max(1, pos_count)
    crit = nn.CrossEntropyLoss(weight=torch.tensor([1.0, pos_w], dtype=torch.float32))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=1e-4)
    best_auc, best_state = -1.0, None
    t0 = time.perf_counter()
    for ep in range(1, epochs + 1):
        model.train()
        tot = 0.0
        for xb, yb in train_loader:
            opt.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            opt.step()
            tot += float(loss.item()) * len(yb)
        vp, vl, _ = get_probs(model, val_loader)
        auc = float(roc_auc_score(vl, vp))
        _, vf1 = best_threshold(vp, vl)
        print(
            f"[{name}] Ep {ep:02d}/{epochs} | loss={tot / total_train:.4f} | val_AUC={auc:.3f} | val_DefectF1={vf1:.3f}",
            flush=True,
        )
        if auc > best_auc:
            best_auc = auc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    train_s = time.perf_counter() - t0
    assert best_state is not None
    model.load_state_dict(best_state)
    vp, vl, _ = get_probs(model, val_loader)
    thr, _ = best_threshold(vp, vl)
    tp, tl, ms = get_probs(model, test_loader)
    pred = (tp >= thr).astype(int)

    metrics = {
        "name": name,
        "arch": arch,
        "threshold": round(thr, 4),
        "defect_recall": round(float(recall_score(tl, pred, zero_division=0)), 4),
        "defect_f1": round(float(f1_score(tl, pred, zero_division=0)), 4),
        "defect_precision": round(float(precision_score(tl, pred, zero_division=0)), 4),
        "macro_f1": round(float(f1_score(tl, pred, average="macro", zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(tl, tp)), 4),
        "overall_accuracy_pct": round(float(accuracy_score(tl, pred) * 100.0), 2),
        "inference_ms": round(float(ms), 2),
        "train_seconds": round(float(train_s), 1),
        "confusion_matrix": confusion_matrix(tl, pred).tolist(),
    }
    print(f"TEST {json.dumps(metrics)}", flush=True)
    return model, metrics


class TwoOutputResNet18(nn.Module):
    """Exports (logits [B, 2], conv_maps [B, 512, 7, 7]) for ONNX + Grad-CAM."""

    def __init__(self, base: models.ResNet) -> None:
        super().__init__()
        self.stem = nn.Sequential(base.conv1, base.bn1, base.relu, base.maxpool)
        self.layer1 = base.layer1
        self.layer2 = base.layer2
        self.layer3 = base.layer3
        self.layer4 = base.layer4
        self.avgpool = base.avgpool
        self.fc = base.fc

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.stem(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        conv_maps = self.layer4(x)
        pooled = self.avgpool(conv_maps).flatten(1)
        logits = self.fc(pooled)
        return logits, conv_maps


class TwoOutputMobileNetV3(nn.Module):
    """Exports (logits [B, 2], conv_maps [B, 576, 7, 7]) for ONNX + Grad-CAM."""

    def __init__(self, base: models.MobileNetV3) -> None:
        super().__init__()
        self.features = base.features
        self.avgpool = base.avgpool
        self.classifier = base.classifier

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        conv_maps = self.features(x)
        pooled = self.avgpool(conv_maps).flatten(1)
        logits = self.classifier(pooled)
        return logits, conv_maps


def export_held_out_samples(pos_te: list[dict], neg_te: list[dict]) -> list[dict]:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    chosen: list[dict] = []

    # Prefer up to 4 distinct defect types from held-out test split, prioritizing larger visible defect regions
    seen_codes: set[str] = set()
    sorted_pos = sorted(pos_te, key=lambda x: x["defect_px"], reverse=True)
    for item in sorted_pos:
        if item["code"] not in seen_codes:
            chosen.append(item)
            seen_codes.add(item["code"])
        if len(chosen) >= 4:
            break
    if len(chosen) < 4:
        for item in sorted_pos:
            if item not in chosen:
                chosen.append(item)
            if len(chosen) >= 4:
                break

    # Pick 2 distinct clean weaves from held-out test split
    seen_weaves: set[str] = set()
    clean_picks: list[dict] = []
    for item in neg_te:
        if item["strip_id"].startswith("0"):
            continue  # prefer pure NODefect weave images for clean reference cards
        weave = item["strip_id"].split("/")[0]
        if weave not in seen_weaves:
            clean_picks.append(item)
            seen_weaves.add(weave)
        if len(clean_picks) >= 2:
            break
    if len(clean_picks) < 2:
        for item in neg_te:
            if item not in clean_picks:
                clean_picks.append(item)
            if len(clean_picks) >= 2:
                break

    samples_meta: list[dict] = []
    for idx, item in enumerate(chosen, start=1):
        code = item["code"]
        label = AITEX_CODE_NAMES.get(code, f"Defect {code}")
        fname = f"sample_defect_{idx}_{code}.png"
        item["raw"].save(SAMPLES_DIR / fname)
        samples_meta.append({
            "id": f"aitex_defect_{idx}",
            "title": f"{label} (AITEX #{idx})",
            "defect_code": code,
            "ground_truth_label": label,
            "is_defect": True,
            "filename": fname,
        })

    for idx, item in enumerate(clean_picks, start=1):
        fname = f"sample_clean_{idx}.png"
        item["raw"].save(SAMPLES_DIR / fname)
        samples_meta.append({
            "id": f"aitex_clean_{idx}",
            "title": f"Clean Grey Cloth #{idx}",
            "defect_code": "clean",
            "ground_truth_label": "Clean Cloth",
            "is_defect": False,
            "filename": fname,
        })

    return samples_meta


def main() -> None:
    os.environ["OMP_NUM_THREADS"] = "8"
    torch.set_num_threads(max(4, os.cpu_count() or 8))
    parser = argparse.ArgumentParser()
    parser.add_argument("--aitex-dir", type=Path, default=DEFAULT_AITEX_DIR)
    args = parser.parse_args()

    set_seed(SEED)
    VISION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    defect_strips, clean_strips = load_strips(args.aitex_dir)
    random.shuffle(defect_strips)
    random.shuffle(clean_strips)

    d_tr, d_va, d_te = split_list(defect_strips)
    c_tr, c_va, c_te = split_list(clean_strips)

    pos_tr, neg_tr = extract_patches(d_tr, c_tr, extra_train_defect_shifts=True)
    random.shuffle(neg_tr)
    train_items = pos_tr + neg_tr[: len(pos_tr) * 2]

    pos_va, neg_va = extract_patches(d_va, c_va, extra_train_defect_shifts=False)
    val_items = pos_va + neg_va

    pos_te, neg_te = extract_patches(d_te, c_te, extra_train_defect_shifts=False)
    test_items = pos_te + neg_te

    print(
        f"Split | Train strips: {len(d_tr)}d+{len(c_tr)}c -> {len(train_items)} patches | "
        f"Val: {len(d_va)}d+{len(c_va)}c -> {len(val_items)} | "
        f"Test: {len(d_te)}d+{len(c_te)}c -> {len(test_items)} ({len(pos_te)} defect / {len(neg_te)} clean)",
        flush=True,
    )

    train_tf = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(),
        T.ColorJitter(brightness=0.12, contrast=0.12),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    eval_tf = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_loader = DataLoader(MemDataset(train_items, train_tf), batch_size=32, shuffle=True)
    val_loader = DataLoader(MemDataset(val_items, eval_tf), batch_size=64, shuffle=False)
    test_loader = DataLoader(MemDataset(test_items, eval_tf), batch_size=64, shuffle=False)

    m_mob = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    for p in m_mob.features[:6].parameters():
        p.requires_grad = False
    m_mob.classifier[-1] = nn.Linear(m_mob.classifier[-1].in_features, 2)
    m_mob, mob_metrics = train_and_eval(
        "MobileNetV3-Small + CLAHE",
        "mobilenet_v3_small",
        m_mob,
        train_loader,
        val_loader,
        test_loader,
        len(pos_tr),
        len(train_items),
        epochs=6,
        lr=6e-4,
    )

    m_res = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    for layer in (m_res.conv1, m_res.bn1, m_res.layer1, m_res.layer2):
        for p in layer.parameters():
            p.requires_grad = False
    m_res.fc = nn.Linear(m_res.fc.in_features, 2)
    m_res, res_metrics = train_and_eval(
        "ResNet-18 + CLAHE",
        "resnet18",
        m_res,
        train_loader,
        val_loader,
        test_loader,
        len(pos_tr),
        len(train_items),
        epochs=6,
        lr=5e-4,
    )

    # Select single winning model by held-out Defect-F1 (tie-break ROC-AUC)
    if (res_metrics["defect_f1"], res_metrics["roc_auc"]) >= (mob_metrics["defect_f1"], mob_metrics["roc_auc"]):
        win_metrics = res_metrics
        wrapper: nn.Module = TwoOutputResNet18(m_res)
        w = m_res.fc.weight.detach().cpu()
        cam_weights = (w[1] - w[0]).tolist()
    else:
        win_metrics = mob_metrics
        wrapper = TwoOutputMobileNetV3(m_mob)
        w1 = m_mob.classifier[0].weight.detach().cpu()  # [1024, 576]
        w2 = m_mob.classifier[3].weight.detach().cpu()  # [2, 1024]
        eff = w2 @ w1  # linear approximation for CAM channel importance
        cam_weights = (eff[1] - eff[0]).tolist()

    wrapper.eval()
    onnx_path = VISION_OUT_DIR / "winning_model.onnx"
    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        wrapper,
        dummy,
        str(onnx_path),
        dynamo=False,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["image"],
        output_names=["logits", "conv_maps"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}, "conv_maps": {0: "batch"}},
    )
    print(f"Exported Two-Output ONNX: {onnx_path} ({onnx_path.stat().st_size / 1e6:.2f} MB)", flush=True)

    samples_meta = export_held_out_samples(pos_te, neg_te)

    model_card = {
        "winning_model_name": win_metrics["name"],
        "model_version": f"{win_metrics['arch']}-clahe-v1",
        "architecture": win_metrics["arch"],
        "threshold": win_metrics["threshold"],
        "input_size": [224, 224],
        "cam_weights": [round(float(v), 6) for v in cam_weights],
        "held_out_split_summary": {
            "train_strips": len(d_tr) + len(c_tr),
            "val_strips": len(d_va) + len(c_va),
            "test_strips": len(d_te) + len(c_te),
            "train_defect_strips": len(d_tr),
            "train_clean_strips": len(c_tr),
            "val_defect_strips": len(d_va),
            "val_clean_strips": len(c_va),
            "test_defect_strips": len(d_te),
            "test_clean_strips": len(c_te),
            "test_total_patches": len(test_items),
            "test_defect_patches": len(pos_te),
            "test_clean_patches": len(neg_te),
            "imbalance_note": (
                f"Overall accuracy ({win_metrics['overall_accuracy_pct']}%) is high partly because "
                f"{round(len(neg_te) * 100.0 / max(1, len(test_items)), 1)}% ({len(neg_te)}/{len(test_items)}) "
                f"of held-out patches are clean; evaluate primarily using Defect Recall ({win_metrics['defect_recall']}) "
                f"and Defect F1 ({win_metrics['defect_f1']})."
            ),
        },
        "comparison": [res_metrics, mob_metrics],
        "samples": samples_meta,
    }
    card_path = VISION_OUT_DIR / "model_card.json"
    card_path.write_text(json.dumps(model_card, indent=2), encoding="utf-8")
    print(f"Saved model card: {card_path}", flush=True)


if __name__ == "__main__":
    main()
