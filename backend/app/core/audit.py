"""Immutable audit logging and soft-delete helpers for financial and master records."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.core import AuditLog


def _serialize_value(val: Any) -> Any:
    """Convert database values cleanly to JSON-compatible primitives."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return str(val)
    return val


def snapshot_fields(obj: Any, fields: list[str]) -> dict[str, Any]:
    """Capture a deterministic dictionary snapshot of selected model attributes."""
    return {field: _serialize_value(getattr(obj, field)) for field in fields}


def record_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    changed_by: int,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    """Append an immutable entry to audit_logs."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_by=changed_by,
        changed_at=datetime.now(timezone.utc),
        old_values_json=json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
        new_values_json=json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        reason=reason,
    )
    db.add(entry)
    return entry


def soft_delete_record(
    db: Session,
    *,
    obj: Any,
    entity_type: str,
    entity_id: int,
    user_id: int,
    reason: str,
    audit_fields: list[str],
) -> AuditLog:
    """Soft-delete a financial/config record and record old/new state in audit_logs."""
    old_snap = snapshot_fields(obj, audit_fields)
    now = datetime.now(timezone.utc)
    obj.is_deleted = True
    obj.deleted_at = now
    obj.deleted_by = user_id
    if hasattr(obj, "delete_reason"):
        obj.delete_reason = reason
    new_snap = snapshot_fields(obj, audit_fields)
    new_snap["is_deleted"] = True
    new_snap["delete_reason"] = reason
    return record_audit(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action="SOFT_DELETE",
        changed_by=user_id,
        old_values=old_snap,
        new_values=new_snap,
        reason=reason,
    )
