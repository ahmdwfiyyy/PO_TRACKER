"""Password hashing, login tokens and brute-force protection."""
import time
from datetime import timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.db import utcnow

ALGORITHM = "HS256"
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd.verify(password, hashed)


def create_token(user_id: int, role: str, name: str, vendor_id: int | None) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "vendor_id": vendor_id,
        "exp": utcnow() + timedelta(hours=settings.token_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError."""
    return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])


# --------------------------------------------------------------------------- brute-force protection
# Kept in memory: fine for a single backend container.
MAX_FAILURES = 5
LOCK_SECONDS = 5 * 60
_failures: dict[str, list[float]] = {}


def is_locked(key: str) -> bool:
    recent = [t for t in _failures.get(key, []) if time.time() - t < LOCK_SECONDS]
    _failures[key] = recent
    return len(recent) >= MAX_FAILURES


def record_failure(key: str) -> None:
    _failures.setdefault(key, []).append(time.time())


def clear_failures(key: str | None = None) -> None:
    if key is None:
        _failures.clear()
    else:
        _failures.pop(key, None)
