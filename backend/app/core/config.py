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
    enable_api_docs: bool = True
    protected_demo_usernames: str = "welcome123,welcome@123"
    # Private In-App LOOMOS AI Copilot (Gemini) — strictly allowlisted usernames only
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_pro_model: str = "gemini-3.5-flash"
    gemini_fallback_models: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.6-flash,gemini-3.7-flash"
    ai_allowed_usernames: str = ""

    def is_demo_active(self) -> bool:
        """Return True whenever running against the isolated demo database."""
        return bool(self.demo_mode or self.db_path.name.lower() == "loomos_demo.db")

    def protected_demo_username_set(self) -> set[str]:
        """Demo accounts whose passwords/active flags cannot be vandalized by public demo visitors."""
        return {u.strip().lower() for u in self.protected_demo_usernames.split(",") if u.strip()}

    def ai_allowed_username_set(self) -> set[str]:
        """Return lowercase set of usernames explicitly granted private AI Copilot access."""
        return {u.strip().lower() for u in self.ai_allowed_usernames.split(",") if u.strip()}

    def is_ai_allowed_username(self, username: str) -> bool:
        return bool(username and username.strip().lower() in self.ai_allowed_username_set())

    def is_ai_allowed_user(self, user: object) -> bool:
        """Return True ONLY for active OWNER accounts listed in LOOMOS_AI_ALLOWED_USERNAMES."""
        return bool(
            getattr(user, "is_active", False)
            and getattr(user, "role", "") == "OWNER"
            and self.is_ai_allowed_username(getattr(user, "username", ""))
        )

    def is_ai_configured(self) -> bool:
        """Return True when a Gemini API key is configured on this server."""
        return bool(self.gemini_api_key.strip())

    def ai_model_chain(self, mode: str = "fast") -> list[str]:
        """Return ordered deduplicated Gemini model chain with automatic fallback."""
        fallbacks = [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]
        if mode == "deep":
            heads = [self.gemini_pro_model.strip(), self.gemini_model.strip()]
        else:
            heads = [self.gemini_model.strip(), "gemini-3.1-flash-lite", self.gemini_pro_model.strip()]
        ordered: list[str] = []
        for m in [*heads, *fallbacks]:
            if m and m not in ordered:
                ordered.append(m)
        return ordered or ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

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
