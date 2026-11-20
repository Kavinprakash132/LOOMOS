"""Train & benchmark multi-dataset RGB textile defect models (EfficientNet-B0 vs MobileNetV3-Large)
across 6 real fabric defect corpora (~20,000+ images: aazgr balanced color defects, ITD 10-fabric color set,
real smartphone camera photos, MVTec woven carpet, DS-Cotton-Fabric, and local AITEX powerloom strips).

Exports the winning Two-Output (logits [B, 2], conv_maps [B, C, 7, 7]) ONNX model, updated model_card.json,
and 6 diverse held-out reference samples (color + powerloom) to backend/data/vision/.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import socket
import time
from collections import Counter, defaultdict
from pathlib import Path

# Force IPv4 so Windows IPv6 never stalls torchvision pretrained weight downloads
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    v4 = [r for r in res if r[0] == socket.AF_INET]
    return v4 or res


socket.getaddrinfo = _ipv4_getaddrinfo

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
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

SEED = 42
DEFAULT_MANIFEST = Path(
    r"C:\Users\praka\.gemini\antigravity\brain\dd8df6b2-d122-4817-8f8a-86e471411396\scratch\fabric_corpus\manifest.jsonl"
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
VISION_OUT_DIR = BACKEND_ROOT / "data" / "vision"
SAMPLES_DIR = VISION_OUT_DIR / "samples"

SOURCE_TARGET_WEIGHTS: dict[str, float] = {
    "aazgr_balanced": 0.30,
    "itd_color": 0.22,
    "zju_leaper": 0.20,
    "aitex": 0.16,
    "phone_camera": 0.10,
    "ds_cotton": 0.02,
}

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


def load_manifest(path: Path) -> list[dict]:
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if os.path.exists(rec["path"]):
                records.append(rec)
    return records


def leak_free_stratified_split(records: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split 70/15/15 by (source, group_id) so zero strip/image leakage occurs between splits."""
    by_src_grp: dict[tuple[str, int], list[tuple[str, list[dict]]]] = defaultdict(list)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        grouped[(r["source"], r["group_id"])].append(r)

    for (src, gid), items in sorted(grouped.items()):
        # Group majority/defect flag for stratified split
        has_def = 1 if any(it["label"] == 1 for it in items) else 0
        by_src_grp[(src, has_def)].append((gid, items))

    rng = random.Random(SEED)
    train_recs: list[dict] = []
    val_recs: list[dict] = []
    test_recs: list[dict] = []

    for key, group_list in sorted(by_src_grp.items()):
        rng.shuffle(group_list)
        n = len(group_list)
        n_tr = max(1, int(round(0.70 * n)))
        n_va = max(1, int(round(0.15 * n))) if n >= 3 else 0
        if n_tr + n_va >= n and n >= 3:
            n_tr = max(1, n - 2)
            n_va = 1
        tr_g = group_list[:n_tr]
        va_g = group_list[n_tr : n_tr + n_va]
        te_g = group_list[n_tr + n_va :]

        for _, items in tr_g:
            train_recs.extend(items)
        for _, items in va_g:
            # Exclude shifted training augmentations from val/test on AITEX
            val_recs.extend([it for it in items if it.get("strip_kind") != "defect_shift"])
        for _, items in te_g:
            test_recs.extend([it for it in items if it.get("strip_kind") != "defect_shift"])

    return train_recs, val_recs, test_recs


class DiskFabricDataset(Dataset):
    def __init__(self, records: list[dict], transform: T.Compose) -> None:
        self.records = records
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int):
        rec = self.records[idx]
        with Image.open(rec["path"]) as im:
            img = im.convert("RGB")
        return self.transform(img), int(rec["label"])


def build_balanced_sampler(records: list[dict], samples_per_epoch: int) -> WeightedRandomSampler:
    """Balance sampling across all 6 sources AND 50/50 defect vs clean inside every source."""
    counts = Counter((r["source"], r["label"]) for r in records)
    present_sources = sorted({r["source"] for r in records})
    raw_w = {s: SOURCE_TARGET_WEIGHTS.get(s, 0.05) for s in present_sources}
    w_sum = sum(raw_w.values()) or 1.0
    src_w = {s: v / w_sum for s, v in raw_w.items()}

    sample_weights: list[float] = []
    for r in records:
        s = r["source"]
        lbl = r["label"]
        # Check if both classes exist in this source
        has_both = counts[(s, 0)] > 0 and counts[(s, 1)] > 0
        cls_share = 0.5 if has_both else 1.0
        w = (src_w[s] * cls_share) / max(1, counts[(s, lbl)])
        sample_weights.append(w)

    return WeightedRandomSampler(
        weights=torch.tensor(sample_weights, dtype=torch.double),
        num_samples=samples_per_epoch,
        replacement=True,
    )


def eval_probs(model: nn.Module, loader: DataLoader) -> tuple[np.ndarray, np.ndarray, float]:
    model.eval()
    probs: list[float] = []
    labels: list[int] = []
    t0 = time.perf_counter()
    with torch.no_grad():
        for xb, yb in loader:
            p = torch.softmax(model(xb), dim=1)[:, 1]
            probs.extend(p.numpy().tolist())
            labels.extend(yb.numpy().tolist())
    ms = (time.perf_counter() - t0) * 1000.0 / max(len(labels), 1)
    return np.array(probs, dtype=np.float32), np.array(labels, dtype=np.int64), ms


def find_best_threshold(probs: np.ndarray, labels: np.ndarray, records: list[dict] | None = None) -> tuple[float, float]:
    best_t, best_score = 0.5, -1.0
    src_indices: dict[str, list[int]] = defaultdict(list)
    if records is not None:
        for i, r in enumerate(records):
            src_indices[r["source"]].append(i)
    for t in np.linspace(0.25, 0.85, 31):
        preds = (probs >= t).astype(int)
        overall_f1 = float(f1_score(labels, preds, zero_division=0))
        if records is not None and src_indices:
            per_src_f1s = []
            for idxs in src_indices.values():
                sl = labels[idxs]
                if len(set(sl.tolist())) == 2:
                    per_src_f1s.append(float(f1_score(sl, preds[idxs], zero_division=0)))
            score = 0.55 * overall_f1 + 0.45 * (sum(per_src_f1s) / max(1, len(per_src_f1s)))
        else:
            score = overall_f1
        if score > best_score:
            best_score, best_t = score, float(t)
    return best_t, best_score


def compute_metrics(
    name: str,
    arch: str,
    probs: np.ndarray,
    labels: np.ndarray,
    thr: float,
    ms: float,
    train_s: float,
    records: list[dict],
) -> dict:
    pred = (probs >= thr).astype(int)
    per_source: dict[str, dict] = {}
    sources = sorted({r["source"] for r in records})
    for s in sources:
        idxs = [i for i, r in enumerate(records) if r["source"] == s]
        if not idxs:
            continue
        sp = probs[idxs]
        sl = labels[idxs]
        sd = pred[idxs]
        auc_val = float(roc_auc_score(sl, sp)) if len(set(sl.tolist())) == 2 else None
        per_source[s] = {
            "count": len(idxs),
            "defects": int(sl.sum()),
            "recall": round(float(recall_score(sl, sd, zero_division=0)), 4),
            "precision": round(float(precision_score(sl, sd, zero_division=0)), 4),
            "f1": round(float(f1_score(sl, sd, zero_division=0)), 4),
            "roc_auc": round(auc_val, 4) if auc_val is not None else None,
            "accuracy_pct": round(float(accuracy_score(sl, sd) * 100.0), 2),
        }

    return {
        "name": name,
        "arch": arch,
        "threshold": round(thr, 4),
        "defect_recall": round(float(recall_score(labels, pred, zero_division=0)), 4),
        "defect_f1": round(float(f1_score(labels, pred, zero_division=0)), 4),
        "defect_precision": round(float(precision_score(labels, pred, zero_division=0)), 4),
        "macro_f1": round(float(f1_score(labels, pred, average="macro", zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(labels, probs)), 4),
        "overall_accuracy_pct": round(float(accuracy_score(labels, pred) * 100.0), 2),
        "inference_ms": round(float(ms), 2),
        "train_seconds": round(float(train_s), 1),
        "confusion_matrix": confusion_matrix(labels, pred).tolist(),
        "per_source": per_source,
    }


def train_two_stage(
    name: str,
    arch: str,
    model: nn.Module,
    unfreeze_stage1_fn,
    unfreeze_stage2_fn,
    train_loader: DataLoader,
    val_fast_loader: DataLoader,
    val_fast_records: list[dict],
    val_full_loader: DataLoader,
    val_full_records: list[dict],
    test_loader: DataLoader,
    test_records: list[dict],
    stage1_epochs: int,
    stage2_epochs: int,
    lr_stage1: float,
    lr_stage2: float,
) -> tuple[nn.Module, dict]:
    crit = nn.CrossEntropyLoss(label_smoothing=0.03)
    best_score, best_state = -1.0, None
    t0 = time.perf_counter()

    def run_stage(stage_idx: int, epochs: int, lr: float):
        nonlocal best_score, best_state
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=lr, weight_decay=2e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs), eta_min=lr * 0.05)
        for ep in range(1, epochs + 1):
            model.train()
            tot_loss = 0.0
            n_seen = 0
            ep_t0 = time.perf_counter()
            for xb, yb in train_loader:
                opt.zero_grad()
                loss = crit(model(xb), yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, 2.0)
                opt.step()
                tot_loss += float(loss.item()) * len(yb)
                n_seen += len(yb)
            sched.step()
            vp, vl, _ = eval_probs(model, val_fast_loader)
            auc = float(roc_auc_score(vl, vp))
            _, vf1 = find_best_threshold(vp, vl, val_fast_records)
            score = 0.5 * vf1 + 0.5 * auc
            print(
                f"[{name}] S{stage_idx} Ep {ep:02d}/{epochs} ({time.perf_counter() - ep_t0:.0f}s) | "
                f"loss={tot_loss / max(1, n_seen):.4f} | val_AUC={auc:.4f} | val_balF1={vf1:.4f}",
                flush=True,
            )
            if score > best_score:
                best_score = score
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    unfreeze_stage1_fn(model)
    run_stage(1, stage1_epochs, lr_stage1)

    unfreeze_stage2_fn(model)
    run_stage(2, stage2_epochs, lr_stage2)

    train_s = time.perf_counter() - t0
    assert best_state is not None
    model.load_state_dict(best_state)

    vp, vl, _ = eval_probs(model, val_full_loader)
    thr, _ = find_best_threshold(vp, vl, val_full_records)
    tp, tl, ms = eval_probs(model, test_loader)

    # Benchmark single-image CPU inference latency accurately
    model.eval()
    x1 = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        for _ in range(3):
            model(x1)
        ti = time.perf_counter()
        for _ in range(15):
            model(x1)
        single_ms = (time.perf_counter() - ti) * 1000.0 / 15.0

    metrics = compute_metrics(name, arch, tp, tl, thr, single_ms, train_s, test_records)
    print(f"TEST [{name}] Overall: F1={metrics['defect_f1']} Recall={metrics['defect_recall']} "
          f"Prec={metrics['defect_precision']} AUC={metrics['roc_auc']} Acc={metrics['overall_accuracy_pct']}% "
          f"CPU={single_ms:.1f}ms", flush=True)
    for src, sm in metrics["per_source"].items():
        print(f"   -> {src:16s}: n={sm['count']:4d} (def={sm['defects']:4d}) | F1={sm['f1']} Rec={sm['recall']} Prec={sm['precision']} AUC={sm['roc_auc']}", flush=True)
    return model, metrics


class TwoOutputEfficientNetB0(nn.Module):
    """Exports (logits [B, 2], conv_maps [B, 1280, 7, 7]) for exact ONNX + Grad-CAM."""

    def __init__(self, base: models.EfficientNet) -> None:
        super().__init__()
        self.features = base.features
        self.avgpool = base.avgpool
        self.classifier = base.classifier

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        conv_maps = self.features(x)
        pooled = self.avgpool(conv_maps).flatten(1)
        logits = self.classifier(pooled)
        return logits, conv_maps


class TwoOutputMobileNetV3Large(nn.Module):
    """Exports (logits [B, 2], conv_maps [B, 960, 7, 7]) for ONNX + Grad-CAM."""

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


def export_diverse_samples(test_records: list[dict]) -> list[dict]:
    """Export 6 diverse held-out test samples (4 defects: oil/hole/industrial/loom + 2 clean: color + grey)."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for old_png in SAMPLES_DIR.glob("sample_*.png"):
        old_png.unlink(missing_ok=True)
    samples_meta: list[dict] = []

    def pick_first(predicate) -> dict | None:
        for r in test_records:
            if predicate(r):
                return r
        return None

    defect_specs = [
        ("sample_defect_1_oil", "Oil Stain (Color Cloth)", "OIL", lambda r: r["source"] == "aazgr_balanced" and r["label"] == 1 and "oil" in r["subtype"].lower()),
        ("sample_defect_2_burst", "Hole / Burst Tear", "BURST", lambda r: r["source"] == "aazgr_balanced" and r["label"] == 1 and "burst" in r["subtype"].lower()),
        ("sample_defect_3_itd", "Industrial Color Defect", "ITD", lambda r: r["source"] == "itd_color" and r["label"] == 1),
        ("sample_defect_4_loom", "Powerloom Broken Yarn (AITEX)", "AITEX", lambda r: r["source"] == "aitex" and r["label"] == 1),
    ]
    clean_specs = [
        ("sample_clean_1_color", "Clean Color Fabric", "clean", lambda r: r["source"] in {"aazgr_balanced", "itd_color", "phone_camera"} and r["label"] == 0),
        ("sample_clean_2_loom", "Clean Grey Loom Cloth", "clean", lambda r: r["source"] == "aitex" and r["label"] == 0),
    ]

    used_paths: set[str] = set()
    for idx, (sid, label, code, pred) in enumerate(defect_specs, start=1):
        rec = pick_first(lambda r, p=pred: p(r) and r["path"] not in used_paths) or pick_first(lambda r: r["label"] == 1 and r["path"] not in used_paths)
        if not rec:
            continue
        used_paths.add(rec["path"])
        fname = f"{sid}.png"
        with Image.open(rec["path"]) as im:
            im.convert("RGB").save(SAMPLES_DIR / fname, format="PNG")
        samples_meta.append({
            "id": sid,
            "title": label,
            "defect_code": code,
            "ground_truth_label": label,
            "is_defect": True,
            "filename": fname,
        })

    for idx, (sid, label, code, pred) in enumerate(clean_specs, start=1):
        rec = pick_first(lambda r, p=pred: p(r) and r["path"] not in used_paths) or pick_first(lambda r: r["label"] == 0 and r["path"] not in used_paths)
        if not rec:
            continue
        used_paths.add(rec["path"])
        fname = f"{sid}.png"
        with Image.open(rec["path"]) as im:
            im.convert("RGB").save(SAMPLES_DIR / fname, format="PNG")
        samples_meta.append({
            "id": sid,
            "title": label,
            "defect_code": code,
            "ground_truth_label": label,
            "is_defect": False,
            "filename": fname,
        })

    return samples_meta


def main() -> None:
    os.environ["OMP_NUM_THREADS"] = "10"
    torch.set_num_threads(max(4, min(10, os.cpu_count() or 8)))
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--samples-per-epoch", type=int, default=4800)
    parser.add_argument("--stage1-epochs", type=int, default=2)
    parser.add_argument("--stage2-epochs", type=int, default=5)
    args = parser.parse_args()

    set_seed(SEED)
    VISION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    records = load_manifest(args.manifest)
    train_recs, val_recs, test_recs = leak_free_stratified_split(records)
    print(
        f"Multi-Dataset Corpus: {len(records)} total | "
        f"Train={len(train_recs)} ({sum(r['label'] for r in train_recs)} def) | "
        f"Val={len(val_recs)} ({sum(r['label'] for r in val_recs)} def) | "
        f"Test={len(test_recs)} ({sum(r['label'] for r in test_recs)} def)",
        flush=True,
    )

    train_tf = T.Compose([
        T.RandomResizedCrop(224, scale=(0.55, 1.0), ratio=(0.82, 1.22)),
        T.RandomHorizontalFlip(0.5),
        T.RandomVerticalFlip(0.5),
        T.RandomApply([T.RandomRotation(20)], p=0.40),
        T.RandomApply([T.RandomPerspective(distortion_scale=0.12, p=1.0)], p=0.25),
        T.ColorJitter(brightness=0.30, contrast=0.30, saturation=0.25, hue=0.05),
        T.RandomGrayscale(p=0.10),
        T.RandomApply([T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.2))], p=0.20),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    eval_tf = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    # Stratified fast-val subset (up to 1,200 images across all sources) for fast per-epoch checkpointing;
    # Full val_recs (~3,600) is always used for final threshold selection!
    rng_val = random.Random(SEED)
    by_sv: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in val_recs:
        by_sv[(r["source"], r["label"])].append(r)
    val_fast_recs: list[dict] = []
    for key, lst in sorted(by_sv.items()):
        lst_copy = list(lst)
        rng_val.shuffle(lst_copy)
        val_fast_recs.extend(lst_copy[:150])

    sampler = build_balanced_sampler(train_recs, args.samples_per_epoch)
    train_loader = DataLoader(DiskFabricDataset(train_recs, train_tf), batch_size=32, sampler=sampler, num_workers=0)
    val_fast_loader = DataLoader(DiskFabricDataset(val_fast_recs, eval_tf), batch_size=64, shuffle=False, num_workers=0)
    val_full_loader = DataLoader(DiskFabricDataset(val_recs, eval_tf), batch_size=64, shuffle=False, num_workers=0)
    test_loader = DataLoader(DiskFabricDataset(test_recs, eval_tf), batch_size=64, shuffle=False, num_workers=0)

    # Candidate 1: MobileNetV3-Large (Multi-Dataset RGB)
    m_mob = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.DEFAULT)
    m_mob.classifier[-1] = nn.Linear(m_mob.classifier[-1].in_features, 2)

    def mob_s1(m):
        for p in m.parameters():
            p.requires_grad = False
        for p in m.features[-3:].parameters():
            p.requires_grad = True
        for p in m.classifier.parameters():
            p.requires_grad = True

    def mob_s2(m):
        for p in m.parameters():
            p.requires_grad = False
        for p in m.features[6:].parameters():
            p.requires_grad = True
        for p in m.classifier.parameters():
            p.requires_grad = True

    m_mob, mob_metrics = train_two_stage(
        "MobileNetV3-Large (Multi-Dataset RGB)",
        "mobilenet_v3_large",
        m_mob,
        mob_s1,
        mob_s2,
        train_loader,
        val_fast_loader,
        val_fast_recs,
        val_full_loader,
        val_recs,
        test_loader,
        test_recs,
        stage1_epochs=args.stage1_epochs,
        stage2_epochs=args.stage2_epochs,
        lr_stage1=1e-3,
        lr_stage2=3e-4,
    )

    # Candidate 2: EfficientNet-B0 (Multi-Dataset RGB)
    m_eff = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    m_eff.classifier[-1] = nn.Linear(m_eff.classifier[-1].in_features, 2)

    def eff_s1(m):
        for p in m.parameters():
            p.requires_grad = False
        for p in m.features[-2:].parameters():
            p.requires_grad = True
        for p in m.classifier.parameters():
            p.requires_grad = True

    def eff_s2(m):
        for p in m.parameters():
            p.requires_grad = False
        for p in m.features[4:].parameters():
            p.requires_grad = True
        for p in m.classifier.parameters():
            p.requires_grad = True

    m_eff, eff_metrics = train_two_stage(
        "EfficientNet-B0 (Multi-Dataset RGB)",
        "efficientnet_b0",
        m_eff,
        eff_s1,
        eff_s2,
        train_loader,
        val_fast_loader,
        val_fast_recs,
        val_full_loader,
        val_recs,
        test_loader,
        test_recs,
        stage1_epochs=args.stage1_epochs,
        stage2_epochs=args.stage2_epochs,
        lr_stage1=1e-3,
        lr_stage2=3e-4,
    )

    # Pick winner by held-out Defect-F1 (tie-break ROC-AUC)
    if (eff_metrics["defect_f1"], eff_metrics["roc_auc"]) >= (mob_metrics["defect_f1"], mob_metrics["roc_auc"]):
        win_metrics = eff_metrics
        wrapper: nn.Module = TwoOutputEfficientNetB0(m_eff)
        w = m_eff.classifier[-1].weight.detach().cpu()  # [2, 1280]
        cam_weights = (w[1] - w[0]).tolist()
    else:
        win_metrics = mob_metrics
        wrapper = TwoOutputMobileNetV3Large(m_mob)
        w1 = m_mob.classifier[0].weight.detach().cpu()  # [1280, 960]
        w2 = m_mob.classifier[3].weight.detach().cpu()  # [2, 1280]
        eff = w2 @ w1
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

    samples_meta = export_diverse_samples(test_recs)

    n_sources = len({r["source"] for r in records})
    tr_def = sum(r["label"] for r in train_recs)
    va_def = sum(r["label"] for r in val_recs)
    te_def = sum(r["label"] for r in test_recs)
    te_clean = len(test_recs) - te_def

    def strip_extra(m: dict) -> dict:
        return {k: v for k, v in m.items() if k != "per_source"}

    model_card = {
        "winning_model_name": win_metrics["name"],
        "model_version": f"{win_metrics['arch']}-multidataset-rgb-v2",
        "architecture": win_metrics["arch"],
        "preprocess": "rgb_multiscale",
        "threshold": win_metrics["threshold"],
        "input_size": [224, 224],
        "cam_weights": [round(float(v), 6) for v in cam_weights],
        "dataset_sources": sorted({r["source"] for r in records}),
        "per_source_test_metrics": win_metrics["per_source"],
        "held_out_split_summary": {
            "train_strips": len(train_recs),
            "val_strips": len(val_recs),
            "test_strips": len(test_recs),
            "train_defect_strips": tr_def,
            "train_clean_strips": len(train_recs) - tr_def,
            "val_defect_strips": va_def,
            "val_clean_strips": len(val_recs) - va_def,
            "test_defect_strips": te_def,
            "test_clean_strips": te_clean,
            "test_total_patches": len(test_recs),
            "test_defect_patches": te_def,
            "test_clean_patches": te_clean,
            "imbalance_note": (
                f"Trained across {n_sources} real fabric defect corpora ({len(records):,} total RGB & powerloom images: "
                f"color industrial textiles, smartphone camera cloth photos, cotton fabric slubs, woven carpet, and AITEX loom strips). "
                f"Held-out test ({len(test_recs):,} unseen images: {te_def:,} defect / {te_clean:,} clean) achieved "
                f"Defect Recall {win_metrics['defect_recall']:.3f}, Defect F1 {win_metrics['defect_f1']:.3f}, "
                f"Precision {win_metrics['defect_precision']:.3f}, and ROC-AUC {win_metrics['roc_auc']:.3f}."
            ),
        },
        "comparison": [strip_extra(eff_metrics), strip_extra(mob_metrics)],
        "samples": samples_meta,
    }
    card_path = VISION_OUT_DIR / "model_card.json"
    card_path.write_text(json.dumps(model_card, indent=2), encoding="utf-8")
    print(f"Saved model card: {card_path}", flush=True)


if __name__ == "__main__":
    main()
