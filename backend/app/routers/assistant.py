"""Private LOOMOS AI Copilot endpoints with private per-owner synced conversation history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import AiChatMessage, AiChatThread, User
from app.services.assistant_service import execute_signed_action, run_copilot_chat

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

MAX_COPILOT_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB cap
Image.MAX_IMAGE_PIXELS = 40_000_000

# Lightweight storage guardrails for Azure VM (keeps chat history < ~500 KB)
RETENTION_DAYS = 30
MAX_THREADS_PER_USER = 40
MAX_MESSAGES_PER_THREAD = 100
MAX_STORED_MSG_CHARS = 12_000


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


class StoredActionCard(BaseModel):
    action_type: str
    title: str
    summary: str
    details: list[str] = Field(default_factory=list)
    status: Literal["pending", "executed", "cancelled", "expired"] = "expired"
    feedback: str | None = None


class AssistantChatResponse(BaseModel):
    reply: str
    model_used: str
    tools_used: list[str] = Field(default_factory=list)
    pending_actions: list[PendingActionCard] = Field(default_factory=list)
    thread_id: int | None = None
    thread_title: str | None = None
    user_message_id: int | None = None
    assistant_message_id: int | None = None


class ExecuteActionRequest(BaseModel):
    action_token: str = Field(min_length=16, max_length=8192)
    message_id: int | None = None
    action_index: int | None = None


class ExecuteActionResponse(BaseModel):
    status: str
    action_type: str
    summary: str
    result: dict[str, Any] = Field(default_factory=dict)


class ChatThreadSummary(BaseModel):
    id: int
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatMessageRecord(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    has_image: bool = False
    model_used: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    actions: list[StoredActionCard] = Field(default_factory=list)
    created_at: datetime


class ChatThreadDetail(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageRecord]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _derive_thread_title(message: str, has_image: bool) -> str:
    cleaned = " ".join((message or "").split()).strip()
    if not cleaned:
        return "Photo scan" if has_image else "New chat"
    if len(cleaned) <= 72:
        return cleaned
    return cleaned[:69].rstrip() + "..."


def _prune_user_threads(db: Session, user_id: int) -> None:
    """Keep storage ultra-lightweight: drop threads > 30 days old or exceeding 40 per user."""
    cutoff = _utcnow() - timedelta(days=RETENTION_DAYS)
    expired = db.scalars(
        select(AiChatThread).where(AiChatThread.user_id == user_id, AiChatThread.updated_at < cutoff)
    ).all()
    for t in expired:
        db.delete(t)

    remaining_ids = list(
        db.scalars(
            select(AiChatThread.id)
            .where(AiChatThread.user_id == user_id)
            .order_by(AiChatThread.updated_at.desc(), AiChatThread.id.desc())
        ).all()
    )
    if len(remaining_ids) > MAX_THREADS_PER_USER:
        for stale_id in remaining_ids[MAX_THREADS_PER_USER:]:
            stale = db.get(AiChatThread, stale_id)
            if stale is not None:
                db.delete(stale)


def _trim_thread_messages(db: Session, thread_id: int) -> None:
    msg_ids = list(
        db.scalars(
            select(AiChatMessage.id)
            .where(AiChatMessage.thread_id == thread_id)
            .order_by(AiChatMessage.id.asc())
        ).all()
    )
    overflow = len(msg_ids) - MAX_MESSAGES_PER_THREAD
    if overflow > 0:
        for old_id in msg_ids[:overflow]:
            old_msg = db.get(AiChatMessage, old_id)
            if old_msg is not None:
                db.delete(old_msg)


def _serialize_message(m: AiChatMessage) -> ChatMessageRecord:
    tools: list[str] = []
    if m.tools_used_json:
        try:
            raw_tools = json.loads(m.tools_used_json)
            if isinstance(raw_tools, list):
                tools = [str(x) for x in raw_tools]
        except json.JSONDecodeError:
            tools = []

    actions: list[StoredActionCard] = []
    if m.actions_json:
        try:
            raw_actions = json.loads(m.actions_json)
            if isinstance(raw_actions, list):
                for item in raw_actions:
                    if not isinstance(item, dict):
                        continue
                    saved_status = str(item.get("status") or "expired")
                    # Historical unexecuted proposals cannot be replayed (tokens are never stored in DB)
                    if saved_status == "pending":
                        saved_status = "expired"
                    if saved_status not in {"executed", "cancelled", "expired"}:
                        saved_status = "expired"
                    actions.append(
                        StoredActionCard(
                            action_type=str(item.get("action_type") or ""),
                            title=str(item.get("title") or "Proposed change"),
                            summary=str(item.get("summary") or ""),
                            details=[str(d) for d in (item.get("details") or [])],
                            status=saved_status,  # type: ignore[arg-type]
                            feedback=str(item["feedback"]) if item.get("feedback") else None,
                        )
                    )
        except json.JSONDecodeError:
            actions = []

    return ChatMessageRecord(
        id=m.id,
        role=m.role,  # type: ignore[arg-type]
        content=m.content,
        has_image=bool(m.has_image),
        model_used=m.model_used,
        tools_used=tools,
        actions=actions,
        created_at=m.created_at,
    )


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


@router.get("/threads", response_model=list[ChatThreadSummary])
def list_chat_threads(
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ChatThreadSummary]:
    """List private synced AI chat threads for the signed-in authorized Owner (auto-pruned to 30d / 40 max)."""
    _prune_user_threads(db, owner.id)
    db.commit()

    rows = db.execute(
        select(
            AiChatThread.id,
            AiChatThread.title,
            AiChatThread.created_at,
            AiChatThread.updated_at,
            func.count(AiChatMessage.id).label("message_count"),
        )
        .outerjoin(AiChatMessage, AiChatMessage.thread_id == AiChatThread.id)
        .where(AiChatThread.user_id == owner.id)
        .group_by(AiChatThread.id)
        .order_by(AiChatThread.updated_at.desc(), AiChatThread.id.desc())
        .limit(MAX_THREADS_PER_USER)
    ).all()

    return [
        ChatThreadSummary(
            id=r.id,
            title=r.title,
            message_count=int(r.message_count or 0),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/threads/{thread_id}", response_model=ChatThreadDetail)
def get_chat_thread(
    thread_id: int,
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatThreadDetail:
    """Fetch full messages for a single private thread owned by the current AI owner."""
    thread = db.scalar(
        select(AiChatThread)
        .options(selectinload(AiChatThread.messages))
        .where(AiChatThread.id == thread_id, AiChatThread.user_id == owner.id)
    )
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found")
    return ChatThreadDetail(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=[_serialize_message(m) for m in thread.messages],
    )


@router.delete("/threads/{thread_id}")
def delete_chat_thread(
    thread_id: int,
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Permanently delete a single private chat thread owned by the current AI owner."""
    thread = db.scalar(
        select(AiChatThread).where(AiChatThread.id == thread_id, AiChatThread.user_id == owner.id)
    )
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found")
    db.delete(thread)
    db.commit()
    return {"deleted": True, "id": thread_id}


@router.delete("/threads")
def clear_all_chat_threads(
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Permanently delete all saved AI chat threads for the current AI owner."""
    threads = db.scalars(select(AiChatThread).where(AiChatThread.user_id == owner.id)).all()
    count = len(threads)
    for t in threads:
        db.delete(t)
    db.commit()
    return {"deleted_count": count}


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
    message: str = Form(default=""),
    history_json: str = Form(default="[]"),
    mode: Literal["fast", "deep"] = Form(default="fast"),
    ui_lang: str = Form(default="en"),
    thread_id: int | None = Form(default=None),
    image: UploadFile | None = File(default=None),
) -> AssistantChatResponse:
    """Chat with LOOMOS AI Copilot and persist text-only conversation history per owner."""
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

    clean_message = (message or "").strip()
    if not clean_message and not img_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a message or attach a photo.",
        )

    thread: AiChatThread | None = None
    if thread_id is not None:
        thread = db.scalar(
            select(AiChatThread).where(AiChatThread.id == thread_id, AiChatThread.user_id == owner.id)
        )
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found")
        if not parsed_history:
            prior_msgs = db.scalars(
                select(AiChatMessage)
                .where(AiChatMessage.thread_id == thread.id)
                .order_by(AiChatMessage.id.desc())
                .limit(14)
            ).all()
            parsed_history = [{"role": m.role, "content": m.content} for m in reversed(prior_msgs)]

    result = run_copilot_chat(
        db,
        owner,
        message=clean_message,
        history=parsed_history,
        mode=mode,
        ui_lang=ui_lang if ui_lang in {"en", "ta"} else "en",
        image_bytes=img_bytes,
        image_mime_type=img_mime,
    )

    now = _utcnow()
    if thread is None:
        thread = AiChatThread(
            user_id=owner.id,
            title=_derive_thread_title(clean_message, bool(img_bytes)),
            created_at=now,
            updated_at=now,
        )
        db.add(thread)
        db.flush()
    else:
        thread.updated_at = now

    user_content = clean_message or ("இணைத்த புகைப்படத்தை ஆய்வு செய்" if ui_lang == "ta" else "Analyze attached photo")
    user_row = AiChatMessage(
        thread_id=thread.id,
        role="user",
        content=user_content[:MAX_STORED_MSG_CHARS],
        has_image=bool(img_bytes),
        created_at=now,
    )
    db.add(user_row)

    # Store action previews WITHOUT sensitive action_token so old history can never replay expired writes
    safe_actions = [
        {
            "action_type": str(a.get("action_type") or ""),
            "title": str(a.get("title") or ""),
            "summary": str(a.get("summary") or ""),
            "details": [str(d) for d in (a.get("details") or [])],
            "status": "pending",
        }
        for a in (result.get("pending_actions") or [])
    ]
    assistant_row = AiChatMessage(
        thread_id=thread.id,
        role="assistant",
        content=str(result.get("reply") or "")[:MAX_STORED_MSG_CHARS],
        has_image=False,
        model_used=str(result.get("model_used") or "")[:60] or None,
        tools_used_json=json.dumps(result.get("tools_used") or [], ensure_ascii=False) if result.get("tools_used") else None,
        actions_json=json.dumps(safe_actions, ensure_ascii=False) if safe_actions else None,
        created_at=now,
    )
    db.add(assistant_row)
    db.flush()

    _trim_thread_messages(db, thread.id)
    _prune_user_threads(db, owner.id)
    db.commit()

    return AssistantChatResponse(
        reply=str(result.get("reply") or ""),
        model_used=str(result.get("model_used") or ""),
        tools_used=list(result.get("tools_used") or []),
        pending_actions=[PendingActionCard.model_validate(a) for a in (result.get("pending_actions") or [])],
        thread_id=thread.id,
        thread_title=thread.title,
        user_message_id=user_row.id,
        assistant_message_id=assistant_row.id,
    )


@router.post("/execute", response_model=ExecuteActionResponse)
def execute_assistant_action(
    payload: ExecuteActionRequest,
    owner: Annotated[User, Depends(require_ai_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> ExecuteActionResponse:
    """Execute a previously previewed and HMAC-signed AI Copilot write action."""
    res = execute_signed_action(db, owner, payload.action_token)
    action_type = str(res.get("action_type", ""))
    summary = str(res.get("summary", ""))

    # Optionally persist the "executed" badge on the saved chat message for cross-device history
    if payload.message_id is not None:
        msg = db.scalar(
            select(AiChatMessage)
            .join(AiChatThread, AiChatThread.id == AiChatMessage.thread_id)
            .where(AiChatMessage.id == payload.message_id, AiChatThread.user_id == owner.id)
        )
        if msg and msg.actions_json:
            try:
                cards = json.loads(msg.actions_json)
                if isinstance(cards, list):
                    idx = payload.action_index
                    if idx is not None and 0 <= idx < len(cards) and isinstance(cards[idx], dict):
                        cards[idx]["status"] = "executed"
                        cards[idx]["feedback"] = summary
                    else:
                        for card in cards:
                            if isinstance(card, dict) and card.get("action_type") == action_type and card.get("status") != "executed":
                                card["status"] = "executed"
                                card["feedback"] = summary
                                break
                    msg.actions_json = json.dumps(cards, ensure_ascii=False)
                    db.commit()
            except json.JSONDecodeError:
                pass

    return ExecuteActionResponse(
        status=str(res.get("status", "executed")),
        action_type=action_type,
        summary=summary,
        result={k: v for k, v in res.items() if k not in {"status", "action_type", "summary"}},
    )
