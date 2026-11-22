"""Private LOOMOS AI Copilot endpoints (strictly gated to allowlisted Owner accounts)."""

from __future__ import annotations

import io
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import User
from app.services.assistant_service import execute_signed_action, run_copilot_chat

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

MAX_COPILOT_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB cap
Image.MAX_IMAGE_PIXELS = 40_000_000


def require_ai_owner(owner: Annotated[User, Depends(require_owner)]) -> User:
    """Allow ONLY active OWNER accounts explicitly listed in LOOMOS_AI_ALLOWED_USERNAMES."""
    cfg = get_settings()
    if not cfg.is_ai_allowed_user(owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Private AI Copilot access is restricted to authorized Owner accounts.",
        )
    return owner


class AssistantStatusResponse(BaseModel):
    enabled: bool
    fast_model: str | None = None
    deep_model: str | None = None


class PendingActionCard(BaseModel):
    action_token: str
    action_type: str
    title: str
    summary: str
    details: list[str]


class AssistantChatResponse(BaseModel):
    reply: str
    model_used: str
    tools_used: list[str] = Field(default_factory=list)
    pending_actions: list[PendingActionCard] = Field(default_factory=list)


class ExecuteActionRequest(BaseModel):
    action_token: str = Field(min_length=16, max_length=8192)


class ExecuteActionResponse(BaseModel):
    status: str
    action_type: str
    summary: str
    result: dict[str, Any] = Field(default_factory=dict)


def _prepare_image_bytes(raw_bytes: bytes) -> tuple[bytes, str]:
    """Validate uploaded image and downscale oversized mobile photos to save bandwidth/latency."""
    if len(raw_bytes) > MAX_COPILOT_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image exceeds 15 MB limit.")
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb = img.convert("RGB")
            max_side = 1600
            if max(rgb.size) > max_side:
                rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported or corrupted image file. Please upload a valid JPG/PNG photo.",
        ) from exc


@router.get("/status", response_model=AssistantStatusResponse)
def get_assistant_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssistantStatusResponse:
    """Return whether LOOMOS AI Copilot is unlocked for the currently signed-in account."""
    cfg = get_settings()
    enabled = bool(cfg.is_ai_allowed_user(current_user) and cfg.is_ai_configured())
    if not enabled:
        return AssistantStatusResponse(enabled=False)
    return AssistantStatusResponse(
        enabled=True,
        fast_model=cfg.gemini_model,
        deep_model=cfg.gemini_pro_model,
    )


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
    message: str = Form(default=""),
    history_json: str = Form(default="[]"),
    mode: Literal["fast", "deep"] = Form(default="fast"),
    ui_lang: str = Form(default="en"),
    image: UploadFile | None = File(default=None),
) -> AssistantChatResponse:
    """Chat with LOOMOS AI Copilot (bilingual English/Tamil/Tanglish + live tools + photo OCR)."""
    try:
        parsed_history = json.loads(history_json) if history_json else []
        if not isinstance(parsed_history, list):
            parsed_history = []
    except json.JSONDecodeError:
        parsed_history = []

    img_bytes: bytes | None = None
    img_mime: str | None = None
    if image is not None and image.filename:
        raw = await image.read()
        if raw:
            img_bytes, img_mime = _prepare_image_bytes(raw)

    if not (message or "").strip() and not img_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide a message or attach a photo.")

    result = run_copilot_chat(
        db,
        owner,
        message=message,
        history=parsed_history,
        mode=mode,
        ui_lang=ui_lang if ui_lang in {"en", "ta"} else "en",
        image_bytes=img_bytes,
        image_mime_type=img_mime,
    )
    return AssistantChatResponse.model_validate(result)


@router.post("/execute", response_model=ExecuteActionResponse)
def execute_assistant_action(
    payload: ExecuteActionRequest,
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecuteActionResponse:
    """Execute a previously previewed and HMAC-signed AI Copilot write action."""
    res = execute_signed_action(db, owner, payload.action_token)
    return ExecuteActionResponse(
        status=str(res.get("status", "executed")),
        action_type=str(res.get("action_type", "")),
        summary=str(res.get("summary", "")),
        result={k: v for k, v in res.items() if k not in {"status", "action_type", "summary"}},
    )
