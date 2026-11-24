"""FastAPI dependencies: the signed-in user and role checks.

Every router uses these, so access rules are enforced on the backend, not just hidden in the UI.
"""
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db import get_db
from app.models import Role, User

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Any signed-in, active account. Re-checked against the database on every request,
    so a deactivated account loses access straight away."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Please log in")
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="This account is no longer active")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[..., User]:
    """Dependency factory: only the given roles may call the endpoint."""
    allowed = {str(r) for r in roles}

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have access to this action")
        return user

    return checker


PurchasingUser = Annotated[User, Depends(require_roles(Role.PURCHASING))]
VendorUser = Annotated[User, Depends(require_roles(Role.VENDOR))]
ReceivingUser = Annotated[User, Depends(require_roles(Role.RECEIVING))]
