"""On-demand downloader for public textile defect datasets (AITEX & TILDA_400) in Cloud / Remote Agent VMs.

Usage:
    python scripts/fetch_vision_datasets.py            # Clones AITEX (default) into backend/data/datasets/
    python scripts/fetch_vision_datasets.py --all      # Clones both AITEX and TILDA_400
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = BACKEND_ROOT / "data" / "datasets"

REPOS = {
    "aitex": (
        "https://github.com/jraad/fabric_defect_detection.git",
        DATASETS_DIR / "aitex_repo",
        "data/aitex",
    ),
    "tilda": (
        "https://github.com/the-h-b/TILDA_400.git",
        DATASETS_DIR / "tilda_repo",
        "",
    ),
}


def _clone_if_missing(name: str, repo_url: str, target_dir: Path, subpath: str) -> Path:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    check_path = target_dir / subpath if subpath else target_dir
    if check_path.exists() and any(check_path.iterdir()):
        print(f"[OK] {name.upper()} dataset already present at: {check_path}")
        return check_path

    print(f"[FETCH] Cloning {name.upper()} from {repo_url} into {target_dir} ...")
    res = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"[ERROR] Failed to clone {repo_url}:\n{res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)

    print(f"[DONE] {name.upper()} ready at: {check_path}")
    return check_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public textile vision datasets for LOOMOS Phase 2.")
    parser.add_argument("--all", action="store_true", help="Fetch both AITEX and TILDA_400 datasets.")
    args = parser.parse_args()

    aitex_url, aitex_dir, aitex_sub = REPOS["aitex"]
    _clone_if_missing("aitex", aitex_url, aitex_dir, aitex_sub)

    if args.all:
        tilda_url, tilda_dir, tilda_sub = REPOS["tilda"]
        _clone_if_missing("tilda", tilda_url, tilda_dir, tilda_sub)


if __name__ == "__main__":
    main()
