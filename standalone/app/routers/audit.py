from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserRole
from ..schemas import AuditLogOut
from ..security import require_roles
from ..services import audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def get_audit_logs(
    action: str | None = None,
    entity: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
) -> list[audit.AuditLog]:
    return audit.list_audit_logs(db, limit, offset, action, entity)
