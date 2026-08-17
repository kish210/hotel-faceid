from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse
from ..security import create_access_token, get_current_user, verify_password
from ..services.audit import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip = request.client.host if request.client else None
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not user.active or not verify_password(payload.password, user.password_hash):
        log_action(db, None, "auth.login_failed", entity="user", detail={"username": payload.username}, ip=ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    log_action(db, user, "auth.login", entity="user", entity_id=str(user.id), detail={"username": user.username}, ip=ip)
    return TokenResponse(
        access_token=create_access_token(user),
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
    }
