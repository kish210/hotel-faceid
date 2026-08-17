"""Structured audit logging for operator actions.

Every sensitive write (person update, merge, forget, camera changes, user
administration) is recorded so the hotel can later show who did what and when.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, User

log = logging.getLogger(__name__)


def log_action(
    db: Session,
    user: User | None,
    action: str,
    entity: str | None = None,
    entity_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    try:
        db.add(
            AuditLog(
                user_id=user.id if user else None,
                action=action,
                entity=entity,
                entity_id=entity_id,
                detail=detail,
                ip_address=ip,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Could not write audit log for action %s", action)


def list_audit_logs(
    db: Session,
    limit: int,
    offset: int,
    action: str | None = None,
    entity: str | None = None,
) -> list[AuditLog]:
    from sqlalchemy import select

    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    return list(db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all())
