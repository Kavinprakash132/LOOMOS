"""Authentication, bilingual preference, and Owner-managed user accounts."""

from __future__ import annotations

from collections import defaultdict, deque
import threading
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_owner,
    verify_password,
)
from app.models.core import User
from app.schemas.step1 import (
    AuthTokenResponse,
    LanguageUpdateRequest,
    LoginRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_LOGIN_FAIL_WINDOW_S = 300.0
_LOGIN_MAX_FAILS = 15
_PRIV_FAIL_WINDOW_S = 900.0
_PRIV_MAX_FAILS_IP = 6
_PRIV_MAX_FAILS_GLOBAL = 12
_IP_GLOBAL_WINDOW_S = 600.0
_IP_GLOBAL_MAX_FAILS = 35
_login_failures: dict[str, deque[float]] = defaultdict(deque)
_ip_failures: dict[str, deque[float]] = defaultdict(deque)
_user_failures: dict[str, deque[float]] = defaultdict(deque)
_login_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    """Resolve real client IP resistant to X-Forwarded-For spoofing.

    Caddy sets X-Real-IP from {remote_host}. If absent, prefer the rightmost
    X-Forwarded-For hop (appended by the trusted reverse proxy), else client.host.
    """
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    fwd = request.headers.get("x-forwarded-for", "").strip()
    if fwd:
        hops = [h.strip() for h in fwd.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def _prune(q: deque[float], now: float, window: float) -> None:
    while q and (now - q[0]) > window:
        q.popleft()


def _check_login_rate_limit(ip: str, username: str) -> None:
    cfg = get_settings()
    uname = username.lower()
    is_priv = cfg.is_ai_allowed_username(uname)
    key = f"{ip}:{uname}"
    now = time.monotonic()

    pair_win = _PRIV_FAIL_WINDOW_S if is_priv else _LOGIN_FAIL_WINDOW_S
    pair_max = _PRIV_MAX_FAILS_IP if is_priv else _LOGIN_MAX_FAILS

    with _login_lock:
        q_pair = _login_failures[key]
        _prune(q_pair, now, pair_win)
        if len(q_pair) >= pair_max:
            retry = max(1, int(pair_win - (now - q_pair[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please wait a few minutes and try again.",
                headers={"Retry-After": str(retry)},
            )

        q_ip = _ip_failures[ip]
        _prune(q_ip, now, _IP_GLOBAL_WINDOW_S)
        if len(q_ip) >= _IP_GLOBAL_MAX_FAILS:
            retry = max(1, int(_IP_GLOBAL_WINDOW_S - (now - q_ip[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts from this network. Please wait and try again.",
                headers={"Retry-After": str(retry)},
            )

        if is_priv:
            q_user = _user_failures[uname]
            _prune(q_user, now, _PRIV_FAIL_WINDOW_S)
            if len(q_user) >= _PRIV_MAX_FAILS_GLOBAL:
                retry = max(1, int(_PRIV_FAIL_WINDOW_S - (now - q_user[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Account temporarily locked due to repeated failed login attempts.",
                    headers={"Retry-After": str(retry)},
                )


def _record_login_failure(ip: str, username: str) -> None:
    cfg = get_settings()
    uname = username.lower()
    is_priv = cfg.is_ai_allowed_username(uname)
    key = f"{ip}:{uname}"
    now = time.monotonic()
    pair_win = _PRIV_FAIL_WINDOW_S if is_priv else _LOGIN_FAIL_WINDOW_S

    with _login_lock:
        q_pair = _login_failures[key]
        _prune(q_pair, now, pair_win)
        q_pair.append(now)

        q_ip = _ip_failures[ip]
        _prune(q_ip, now, _IP_GLOBAL_WINDOW_S)
        q_ip.append(now)

        if is_priv:
            q_user = _user_failures[uname]
            _prune(q_user, now, _PRIV_FAIL_WINDOW_S)
            q_user.append(now)


def _clear_login_failures(ip: str, username: str) -> None:
    uname = username.lower()
    with _login_lock:
        _login_failures.pop(f"{ip}:{uname}", None)
        _user_failures.pop(uname, None)


def _serialize_user(user: User) -> UserResponse:
    cfg = get_settings()
    resp = UserResponse.model_validate(user)
    resp.ai_enabled = bool(cfg.is_ai_allowed_user(user) and cfg.is_ai_configured())
    return resp


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokenResponse:
    """Authenticate an active Owner or Supervisor and return a Bearer JWT."""
    uname = payload.username.strip()
    client_ip = _client_ip(request)
    _check_login_rate_limit(client_ip, uname)

    user = db.scalar(select(User).where(User.username == uname))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        _record_login_failure(client_ip, uname)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    _clear_login_failures(client_ip, uname)
    token = create_access_token(user.id, user.username, user.role)
    return AuthTokenResponse(access_token=token, user=_serialize_user(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """Return the authenticated user's profile."""
    return _serialize_user(current_user)


@router.patch("/me/language", response_model=UserResponse)
def update_my_language(
    payload: LanguageUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Switch the current user's UI/payslip language between English and Tamil."""
    current_user.preferred_lang = payload.preferred_lang
    db.commit()
    db.refresh(current_user)
    return _serialize_user(current_user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserResponse]:
    """List Owner and Supervisor accounts (hiding private AI-allowlisted accounts from non-allowlisted Owners)."""
    cfg = get_settings()
    caller_is_ai = cfg.is_ai_allowed_user(owner)
    rows = db.scalars(select(User).order_by(User.id)).all()
    if not caller_is_ai:
        rows = [r for r in rows if not cfg.is_ai_allowed_username(r.username)]
    return [_serialize_user(r) for r in rows]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Create a Supervisor (or additional Owner) account."""
    cfg = get_settings()
    uname = payload.username.strip()
    if cfg.is_ai_allowed_username(uname) and not cfg.is_ai_allowed_user(owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This username is reserved")
    if db.scalar(select(User.id).where(User.username == uname)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(
        full_name=payload.full_name.strip(),
        username=uname,
        password_hash=hash_password(payload.password),
        role=payload.role,
        preferred_lang=payload.preferred_lang,
        is_active=True,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        entity_type="user",
        entity_id=user.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(user, ["username", "role", "is_active"]),
    )
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Update a team member's active status, name, language, or password."""
    cfg = get_settings()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if cfg.is_ai_allowed_username(user.username) and not cfg.is_ai_allowed_user(owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if (
        cfg.is_demo_active()
        and user.username.strip().lower() in cfg.protected_demo_username_set()
        and not cfg.is_ai_allowed_user(owner)
        and (payload.password is not None or payload.is_active is False)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public demo login credentials cannot be changed or disabled in Demo Mode.",
        )
    if user.id == owner.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    old_snap = snapshot_fields(user, ["full_name", "is_active", "preferred_lang"])
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.preferred_lang is not None:
        user.preferred_lang = payload.preferred_lang
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    new_snap = snapshot_fields(user, ["full_name", "is_active", "preferred_lang"])
    record_audit(
        db,
        entity_type="user",
        entity_id=user.id,
        action="UPDATE",
        changed_by=owner.id,
        old_values=old_snap,
        new_values=new_snap,
    )
    db.commit()
    db.refresh(user)
    return _serialize_user(user)
