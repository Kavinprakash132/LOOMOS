"""Authentication, bilingual preference, and Owner-managed user accounts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields
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


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> AuthTokenResponse:
    """Authenticate an active Owner or Supervisor and return a Bearer JWT."""
    user = db.scalar(select(User).where(User.username == payload.username.strip()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user.id, user.username, user.role)
    return AuthTokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current_user)


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
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserResponse]:
    """List all Owner and Supervisor accounts (Owner only)."""
    rows = db.scalars(select(User).order_by(User.id)).all()
    return [UserResponse.model_validate(r) for r in rows]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Create a Supervisor (or additional Owner) account."""
    if db.scalar(select(User.id).where(User.username == payload.username.strip())):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(
        full_name=payload.full_name.strip(),
        username=payload.username.strip(),
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
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Update a team member's active status, name, language, or password."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
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
    return UserResponse.model_validate(user)
