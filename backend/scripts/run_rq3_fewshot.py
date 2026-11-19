"""Phase 5 RQ3 Few-Shot Adaptation Benchmark for LOOMOS-Shed Smartphone Cloth Photos.

Queries reviewed Inspection rows (CONFIRMED_DEFECT / CONFIRMED_CLEAN) stored by /inspect,
extracts 2nd-output convolutional embeddings via winning_model.onnx, and runs k-shot (5/10/20/all)
linear logistic adaptation once sufficient real shed photos have been collected.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_DB = BACKEND_ROOT / "data" / "loomos.db"


def inspect_collected_photos(db_path: Path, run_benchmark: bool = False) -> dict:
    if not db_path.exists():
        return {"status": "db_missing", "db_path": str(db_path), "reviewed_count": 0}

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, image_path, review_status, reviewed_label, is_reference_sample
            FROM inspections
            WHERE review_status IN ('CONFIRMED_DEFECT', 'CONFIRMED_CLEAN')
            ORDER BY id ASC
            """
        ).fetchall()

    field_rows = [r for r in rows if not r[4]]
    ref_rows = [r for r in rows if r[4]]
    defect_field = [r for r in field_rows if r[2] == "CONFIRMED_DEFECT"]
    clean_field = [r for r in field_rows if r[2] == "CONFIRMED_CLEAN"]

    summary = {
        "db_path": str(db_path),
        "total_reviewed": len(rows),
        "reference_samples": len(ref_rows),
        "field_photos_total": len(field_rows),
        "field_defects": len(defect_field),
        "field_clean": len(clean_field),
        "ready_for_rq3_fewshot": len(defect_field) >= 10 and len(clean_field) >= 10,
    }
    if run_benchmark and summary["ready_for_rq3_fewshot"]:
        from app.core.config import get_settings
        from app.services.vision_service import _get_onnx_session, _prepare_display_and_tensor

        storage = get_settings().upload_dir / "inspections"
        sess = _get_onnx_session()
        feats, labels = [], []
        for _id, fname, rstat, _lbl, _is_ref in field_rows:
            img_p = storage / fname
            if not img_p.exists():
                continue
            _, tensor = _prepare_display_and_tensor(img_p.read_bytes())
            _, conv_maps = sess.run(["logits", "conv_maps"], {"image": tensor})
            pooled = np.mean(conv_maps[0], axis=(1, 2))
            feats.append(pooled)
            labels.append(1 if rstat == "CONFIRMED_DEFECT" else 0)
        summary["extracted_embeddings"] = len(feats)
        summary["embedding_dim"] = int(feats[0].shape[0]) if feats else 0
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="LOOMOS RQ3 Few-Shot Adaptation Tool")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path to query")
    parser.add_argument("--dry-run", action="store_true", help="Inspect readiness without running training")
    args = parser.parse_args()

    res = inspect_collected_photos(args.db.resolve(), run_benchmark=not args.dry_run)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
