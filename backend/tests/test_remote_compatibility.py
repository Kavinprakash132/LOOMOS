"""Tests for Google Antigravity Remote Agents compatibility (relative paths, env vars, Gemini config, static SPA)."""

from __future__ import annotations

import os
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import BACKEND_ROOT, Settings, get_settings
from app.main import create_app


def test_relative_paths_resolve_against_backend_root_from_any_cwd(monkeypatch, tmp_path: Path) -> None:
    """Running CLI or server from repo root or another directory must still resolve ./data/* inside backend/."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOOMOS_DB_PATH", "./data/loomos_demo.db")
    monkeypatch.setenv("LOOMOS_BACKUP_DIR", "./data/backups")
    monkeypatch.setenv("LOOMOS_UPLOAD_DIR", "./data/uploads")
    get_settings.cache_clear()
    try:
        cfg = get_settings()
        assert cfg.db_path == (BACKEND_ROOT / "data" / "loomos_demo.db").resolve()
        assert cfg.backup_dir == (BACKEND_ROOT / "data" / "backups").resolve()
        assert cfg.upload_dir == (BACKEND_ROOT / "data" / "uploads").resolve()
        assert cfg.is_demo_active() is True
    finally:
        monkeypatch.delenv("LOOMOS_DB_PATH", raising=False)
        monkeypatch.delenv("LOOMOS_BACKUP_DIR", raising=False)
        monkeypatch.delenv("LOOMOS_UPLOAD_DIR", raising=False)
        get_settings.cache_clear()


def test_gemini_api_key_and_database_url_restored_from_environment(monkeypatch) -> None:
    """Verify GEMINI_API_KEY and LOOMOS_DATABASE_URL can be securely restored via environment variables."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-cloud-secret-key-not-real")
    monkeypatch.setenv("LOOMOS_GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("LOOMOS_DATABASE_URL", "sqlite:///custom_cloud.db")

    cfg = Settings()
    assert cfg.gemini_api_key == "test-cloud-secret-key-not-real"
    assert cfg.gemini_model == "gemini-2.5-pro"
    assert cfg.is_gemini_configured() is True
    assert cfg.resolved_database_url() == "sqlite:///custom_cloud.db"

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg_empty = Settings(gemini_api_key="")
    assert cfg_empty.is_gemini_configured() is False


def test_single_port_spa_fallback_preserves_api_404() -> None:
    """Ensure API 404s remain JSON 404s even when static SPA serving is enabled."""
    app = create_app()
    with TestClient(app) as tc:
        health = tc.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        missing_api = tc.get("/api/v1/nonexistent-endpoint")
        assert missing_api.status_code == 404
