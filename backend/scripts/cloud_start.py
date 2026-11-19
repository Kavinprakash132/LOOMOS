"""Cloud container entrypoint: runs Alembic migrations, optional first-boot demo seed, then Uvicorn."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def _needs_initial_demo_seed(db_path: Path) -> bool:
    if os.environ.get("LOOMOS_AUTO_SEED_DEMO", "false").lower() not in {"1", "true", "yes"}:
        return False
    if not db_path.exists():
        return True
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT COUNT(*) FROM unit_settings")
        count = cur.fetchone()[0]
        conn.close()
        return count == 0
    except Exception:
        return True


def main() -> None:
    os.chdir(BACKEND_DIR)
    from app.core.config import get_settings

    cfg = get_settings()
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.upload_dir.mkdir(parents=True, exist_ok=True)
    cfg.backup_dir.mkdir(parents=True, exist_ok=True)

    # Always apply database migrations cleanly before booting Uvicorn
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    # Optional cloud demo auto-seed on empty DB (safe: only runs if unit_settings has 0 rows)
    if _needs_initial_demo_seed(cfg.db_path):
        from scripts.seed_demo_cli import populate_demo_shed

        print(f"[CLOUD START] Empty demo DB detected at {cfg.db_path} — seeding 5-loom demo sandbox...", flush=True)
        populate_demo_shed(cfg.db_path)

    port = os.environ.get("PORT", "8000")
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
    )


if __name__ == "__main__":
    main()
