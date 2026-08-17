import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserRole
from ..schemas import PasswordChange, UserCreate, UserOut, UserUpdate
from ..security import (
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from ..services.audit import log_action

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin)),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> User:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=payload.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(db, actor, "user.create", entity="user", entity_id=str(user.id), detail={"username": user.username})
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        updates["password_hash"] = hash_password(updates.pop("password"))

    for field, value in updates.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    log_action(db, actor, "user.update", entity="user", entity_id=str(user.id), detail={"username": user.username})
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.admin)),
) -> None:
    if actor.id == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete yourself")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    db.delete(user)
    db.commit()
    log_action(db, actor, "user.delete", entity="user", entity_id=str(user_id), detail={"username": user.username})


# --------------------------------------------------------- own credentials
@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    log_action(db, user, "user.change_password", entity="user", entity_id=str(user.id))
