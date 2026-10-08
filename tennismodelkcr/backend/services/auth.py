"""Authentication service — JWT tokens + invite-code user registration."""
import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import settings

# ── Constants ────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"
USERS_FILE = Path(os.environ.get("USERS_FILE", "/tmp/users.json"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# ── User store (flat JSON — swap for DB in v2) ───────────────────────────────
def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2))


# ── Core helpers ─────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_password_hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


# ── Public API ────────────────────────────────────────────────────────────────
def register_user(username: str, password: str, invite_code: str) -> dict:
    """Register a new user with an invite code. Returns the created user record."""
    code = invite_code.strip().upper()
    valid_codes = [c.upper() for c in settings.invite_codes_list]
    if code not in valid_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite code",
        )

    users = _load_users()
    if username.lower() in users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    record = {
        "username": username,
        "hashed_password": get_password_hash(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "invite_used": code,
    }
    users[username.lower()] = record
    _save_users(users)
    return record


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return user record if credentials are valid, else None."""
    users = _load_users()
    user = users.get(username.lower())
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency — validates JWT and returns user dict."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    users = _load_users()
    user = users.get(username.lower())
    if user is None:
        raise credentials_exc
    return user
