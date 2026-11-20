"""Application settings loaded from environment variables or local secret store."""

from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Return current timezone-aware timestamp in India Standard Time (UTC+05:30)."""
    return datetime.now(IST_TZ)


def today_ist() -> date:
    """Return current calendar date in India Standard Time (safe inside UTC Docker containers)."""
    return now_ist().date()


def _load_or_create_local_secret(secret_file: Path) -> str:
    """Persist a cryptographically random JWT secret locally if none is configured."""
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if len(stored) >= 32:
            return stored
    generated = secrets.token_urlsafe(48)
    secret_file.write_text(generated, encoding="utf-8")
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return generated


class Settings(BaseSettings):
    """Typed runtime configuration for LOOMOS backend."""

    model_config = SettingsConfigDict(
        env_prefix="LOOMOS_",
        env_file=str(BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    app_name: str = "LOOMOS"
    db_path: Path = DATA_DIR / "loomos.db"
    demo_mode: bool = False
    backup_dir: Path = DATA_DIR / "backups"
    upload_dir: Path = DATA_DIR / "uploads"
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    # Allow localhost and private LAN IP origins by default for Choice 1 (Wi-Fi/LAN)
    cors_origins: list[str] = ["*"]

    def is_demo_active(self) -> bool:
        """Return True whenever running against the isolated demo database."""
        return bool(self.demo_mode or self.db_path.name.lower() == "loomos_demo.db")

    def resolved_secret_key(self) -> str:
        """Return configured secret key or auto-generate a local persistent secret alongside the DB."""
        if self.secret_key and "replace-with-random" not in self.secret_key:
            return self.secret_key
        return _load_or_create_local_secret(self.db_path.parent / ".jwt_secret")


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor."""
    settings = Settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
