"""Tests for Private LOOMOS AI Copilot security isolation, tool execution, and HMAC confirm flow."""

from __future__ import annotations

from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import assistant_service


def _setup_private_ai_env(monkeypatch: pytest.MonkeyPatch, allowed: str = "priv_ai_owner", key: str = "test-key-123") -> None:
    monkeypatch.setenv("LOOMOS_AI_ALLOWED_USERNAMES", allowed)
    monkeypatch.setenv("LOOMOS_GEMINI_API_KEY", key)
    get_settings.cache_clear()


def test_ai_copilot_strict_isolation_and_user_hiding(
    client: TestClient,
    initialized_owner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers, _ = initialized_owner

    # First create the private AI owner while allowlist is unset (simulating DB provisioning)
    priv_res = client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={
            "full_name": "Kavin Private",
            "username": "priv_ai_owner",
            "password": "PrivatePassword@99",
            "role": "OWNER",
        },
    )
    assert priv_res.status_code == 201, priv_res.text
    priv_id = priv_res.json()["id"]

    # Create a Supervisor too
    sup_res = client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={
            "full_name": "Floor Sup",
            "username": "sup_test_ai",
            "password": "SupPassword@1",
            "role": "SUPERVISOR",
        },
    )
    assert sup_res.status_code == 201

    # Enable private AI Copilot strictly for priv_ai_owner
    _setup_private_ai_env(monkeypatch, allowed="priv_ai_owner")
    try:
        # 1. Non-allowlisted demo Owner (owner_ram) sees ai_enabled=False and gets 403 on assistant endpoints
        me_demo = client.get("/api/v1/auth/me", headers=owner_headers).json()
        assert me_demo["ai_enabled"] is False
        assert client.get("/api/v1/assistant/status", headers=owner_headers).json()["enabled"] is False
        assert client.post("/api/v1/assistant/chat", headers=owner_headers, data={"message": "hi"}).status_code == 403
        assert client.post("/api/v1/assistant/execute", headers=owner_headers, json={"action_token": "x" * 24}).status_code == 403

        # 2. Demo Owner CANNOT even see priv_ai_owner in GET /auth/users or tamper with its password!
        demo_users = client.get("/api/v1/auth/users", headers=owner_headers).json()
        assert all(u["username"] != "priv_ai_owner" for u in demo_users)
        tamper = client.patch(
            f"/api/v1/auth/users/{priv_id}",
            headers=owner_headers,
            json={"password": "HackedPassword123"},
        )
        assert tamper.status_code == 404

        # 3. Demo Owner CANNOT register another allowlisted username
        monkeypatch.setenv("LOOMOS_AI_ALLOWED_USERNAMES", "priv_ai_owner,reserved_ai")
        get_settings.cache_clear()
        reg_reserved = client.post(
            "/api/v1/auth/users",
            headers=owner_headers,
            json={"full_name": "Fake", "username": "reserved_ai", "password": "Password123", "role": "OWNER"},
        )
        assert reg_reserved.status_code == 403

        # 4. Supervisor gets 403 on assistant endpoints
        sup_tok = client.post("/api/v1/auth/login", json={"username": "sup_test_ai", "password": "SupPassword@1"}).json()["access_token"]
        sup_headers = {"Authorization": f"Bearer {sup_tok}"}
        assert client.get("/api/v1/assistant/status", headers=sup_headers).json()["enabled"] is False
        assert client.post("/api/v1/assistant/chat", headers=sup_headers, data={"message": "hi"}).status_code == 403

        # 5. Private AI Owner sees ai_enabled=True on login, /auth/me, and /assistant/status
        priv_login = client.post(
            "/api/v1/auth/login",
            json={"username": "priv_ai_owner", "password": "PrivatePassword@99"},
        )
        assert priv_login.status_code == 200
        assert priv_login.json()["user"]["ai_enabled"] is True
        priv_headers = {"Authorization": f"Bearer {priv_login.json()['access_token']}"}
        st = client.get("/api/v1/assistant/status", headers=priv_headers).json()
        assert st["enabled"] is True
        assert st["fast_model"]

        # Private AI Owner DOES see itself in /auth/users
        priv_users = client.get("/api/v1/auth/users", headers=priv_headers).json()
        assert any(u["username"] == "priv_ai_owner" for u in priv_users)
    finally:
        get_settings.cache_clear()


def test_ai_copilot_tool_loop_and_confirm_execute_audit(
    client: TestClient,
    initialized_owner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers, _ = initialized_owner

    # Seed a weaver & enable AI strictly for owner_ram in this test
    w_res = client.post(
        "/api/v1/weavers",
        headers=owner_headers,
        json={"full_name": "Selvam R", "wage_mode": "PER_LOOM_SHIFT", "rate_paise": 7500},
    )
    assert w_res.status_code == 201

    _setup_private_ai_env(monkeypatch, allowed="owner_ram")
    try:
        # Mock Gemini client to simulate: Round 1 read tool -> Round 2 propose_record_advance + propose_add_looms -> Round 3 final reply
        call_idx = {"n": 0}

        class FakeModels:
            def generate_content(self, *, model, contents, config):
                call_idx["n"] += 1
                if call_idx["n"] == 1:
                    fc = SimpleNamespace(name="get_shed_summary", args={"days": 7})
                    part = SimpleNamespace(text=None, thought=False)
                    return SimpleNamespace(
                        function_calls=[fc],
                        candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[part]))],
                        text=None,
                    )
                if call_idx["n"] == 2:
                    fc1 = SimpleNamespace(
                        name="propose_record_advance",
                        args={"weaver_name": "selvam", "amount_rupees": 2000, "note": "Festival advance"},
                    )
                    fc2 = SimpleNamespace(
                        name="propose_add_looms",
                        args={"count": 2, "prefix": "S-", "loom_type": "SHUTTLE", "rated_rpm": 165},
                    )
                    part = SimpleNamespace(text=None, thought=False)
                    return SimpleNamespace(
                        function_calls=[fc1, fc2],
                        candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[part]))],
                        text=None,
                    )
                part = SimpleNamespace(text="Prepared both changes for your approval — tap Confirm & Apply!", thought=False)
                return SimpleNamespace(
                    function_calls=[],
                    candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[part]))],
                    text=part.text,
                )

        monkeypatch.setattr(assistant_service, "_build_genai_client", lambda _key: SimpleNamespace(models=FakeModels()))

        chat_res = client.post(
            "/api/v1/assistant/chat",
            headers=owner_headers,
            data={"message": "selvam ku 2k adv podu nd add 2 shuttle looms rpm 165", "mode": "fast", "ui_lang": "en"},
        )
        assert chat_res.status_code == 200, chat_res.text
        body = chat_res.json()
        assert "get_shed_summary" in body["tools_used"]
        assert "propose_record_advance" in body["tools_used"]
        assert len(body["pending_actions"]) == 2

        # DB MUST NOT be mutated before user taps Confirm!
        assert client.get("/api/v1/advances", headers=owner_headers).json() == []
        assert len(client.get("/api/v1/looms", headers=owner_headers).json()) == 16

        # Forged / tampered token MUST fail with 403
        tok0 = body["pending_actions"][0]["action_token"]
        bad_tok = tok0[:-4] + ("0000" if not tok0.endswith("0000") else "1111")
        assert client.post("/api/v1/assistant/execute", headers=owner_headers, json={"action_token": bad_tok}).status_code == 403

        # Confirm both actions cleanly
        for act in body["pending_actions"]:
            ex = client.post("/api/v1/assistant/execute", headers=owner_headers, json={"action_token": act["action_token"]})
            assert ex.status_code == 200, ex.text
            assert ex.json()["status"] == "executed"

        # Verify DB mutations & Audit Log entries
        advs = client.get("/api/v1/advances", headers=owner_headers).json()
        assert len(advs) == 1
        assert advs[0]["amount_paise"] == 200000
        assert advs[0]["weaver_name"] == "Selvam R"

        looms = client.get("/api/v1/looms", headers=owner_headers).json()
        assert len(looms) == 18
        assert any(l["loom_number"] == "S-13" and l["rated_rpm"] == 165 for l in looms)
        assert any(l["loom_number"] == "S-14" and l["rated_rpm"] == 165 for l in looms)

        logs = client.get("/api/v1/audit-logs?limit=20", headers=owner_headers).json()
        assert any(l.get("reason") == "Applied via LOOMOS AI Copilot" for l in logs)
    finally:
        get_settings.cache_clear()
