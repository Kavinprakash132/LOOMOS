"""Application settings loaded from environment variables or local secret store."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"


def _resolve_backend_path(path_val: Path) -> Path:
    """Resolve relative paths against BACKEND_ROOT so CLI/server works from any working directory."""
    if path_val.is_absolute():
        return path_val
    return (BACKEND_ROOT / path_val).resolve()


def _load_or_create_local_secret(secret_file: Path) -> str:
    """Persist a cryptographically random JWT secret locally if none is configured."""
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if len(stored) >= 32:
            return stored
    generated = secrets.token_urlsafe(48)
    secret_file.write_text(generated, encoding="utf-8")
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
    database_url: str = ""
    demo_mode: bool = False
    backup_dir: Path = DATA_DIR / "backups"
    upload_dir: Path = DATA_DIR / "uploads"
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    # Allow localhost, private LAN IP origins, and cloud preview hosts by default
    cors_origins: list[str] = ["*"]
    serve_static: bool = True

    # Optional Gemini API configuration (restorable via environment variables in cloud/remote agents)
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LOOMOS_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    gemini_model: str = "gemini-2.5-flash"

    def model_post_init(self, __context: object) -> None:
        """Normalize relative paths against BACKEND_ROOT."""
        self.db_path = _resolve_backend_path(self.db_path)
        self.backup_dir = _resolve_backend_path(self.backup_dir)
        self.upload_dir = _resolve_backend_path(self.upload_dir)

    def is_demo_active(self) -> bool:
        """Return True whenever running against the isolated demo database."""
        return bool(self.demo_mode or self.db_path.name.lower() == "loomos_demo.db")

    def is_gemini_configured(self) -> bool:
        """Return True when a non-placeholder Gemini API key is present in the environment."""
        return bool(self.gemini_api_key and "replace-with" not in self.gemini_api_key.lower())

    def resolved_database_url(self) -> str:
        """Return explicit LOOMOS_DATABASE_URL if set, otherwise SQLite URL from db_path."""
        if self.database_url.strip():
            return self.database_url.strip()
        return f"sqlite:///{self.db_path.as_posix()}"

    def resolved_secret_key(self) -> str:
        """Return configured secret key or auto-generate a local persistent secret."""
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
