---
applyTo: "deploy/**,.github/**,backend/app/core/**,backend/app/routers/assistant.py,backend/app/routers/data_ops.py,backend/app/routers/auth.py"
---
# LOOMOS Security, Privacy & Azure Deployment Guardrails

## Hard Security Invariants (Never Weaken!)
1. **Zero Secrets in Git:** Never write API keys, JWT secrets, passwords, private SSH keys, server IPs, private usernames, or payment details into any tracked file, comment, test fixture, or workflow log.
2. **Private AI Copilot Isolation (`require_ai_owner`):**
   - Every `/api/v1/assistant/*` route MUST depend on `require_ai_owner`.
   - Every thread/message query MUST enforce `AiChatThread.user_id == owner.id`.
   - Never persist `action_token` strings or raw uploaded image bytes in `ai_chat_messages`.
   - Preserve automatic retention pruning (30 days, max 40 threads per user, max 100 messages per thread) so SQLite stays tiny on the Azure VM.
3. **Backup Scrubbing & Audit Redaction:**
   - When a non-AI-allowlisted Owner calls `GET /api/v1/backup/sqlite`, `data_ops.py` MUST delete private AI users, nullify their FK references, wipe `ai_chat_messages` and `ai_chat_threads`, scrub AI audit reasons, and execute `VACUUM` so deleted data is unrecoverable even from raw SQLite free pages.
   - Non-AI Owners must never see private AI users in `GET /api/v1/auth/users`, `GET /api/v1/audit-logs`, or CSV exports.
4. **Auth & Demo Protection:**
   - Preserve anti-XFF-spoofing client IP extraction (`request.client.host` / right-most trusted proxy IP) and multi-tier login rate limits (`6 fails / 15 min` on private AI accounts).
   - Preserve demo credential vandalism lock (`LOOMOS_DEMO_MODE=true` blocks non-AI accounts from modifying demo credentials).
   - Keep `/docs` and `/openapi.json` disabled unless `LOOMOS_ENABLE_API_DOCS=true`.

## Azure Production & CI/CD Rules
- Production domain is `https://loomos.tech`; `deploy/azure/Caddyfile` serves `{$LOOMOS_DOMAIN::80}` with HSTS/CSP/X-Frame-Options and permanently redirects `www.loomos.tech` and the legacy Azure hostname to `https://loomos.tech{uri}`.
- Keep `permissions: contents: read` minimal on `.github/workflows/ci-deploy.yml`.
- Never push directly to break `alembic upgrade head`; `backend/scripts/cloud_start.py` runs migrations automatically on container startup.
