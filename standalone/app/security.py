from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user.id), "username": user.username, "role": user.role.value, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise credentials_error from exc

    user = db.get(User, payload.get("sub"))
    if user is None or not user.active:
        raise credentials_error
    return user


def require_roles(*roles: UserRole):
    """Route dependency enforcing role-based access control."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient privileges")
        return user

    return dependency


def require_service_key(x_service_key: str | None = Header(default=None)) -> None:
    """Authenticates the face-service, which has no interactive user."""
    if x_service_key != settings.service_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service key")


# ------------------------------------------------------- secret encryption
def _fernet() -> Fernet | None:
    if not settings.secret_encryption_key:
        return None
    return Fernet(settings.secret_encryption_key.encode())


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    f = _fernet()
    if f is None:  # dev fallback — never run production without a key
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    f = _fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        return None
