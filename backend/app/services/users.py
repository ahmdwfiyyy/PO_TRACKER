"""Creating accounts (used by the users router and seed.py)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Role, User, Vendor
from app.services.errors import ServiceError


def check_password_rules(password: str) -> None:
    minimum = get_settings().min_password_length
    if len(password) < minimum:
        raise ServiceError(f"Password must be at least {minimum} characters")


def create_user(
    db: Session, *, name: str, email: str, password: str, role: Role | str, vendor_id: int | None = None
) -> User:
    role = Role(role)
    email = email.strip().lower()
    check_password_rules(password)
    if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
        raise ServiceError("An account with this email already exists", 409)
    if role == Role.VENDOR:
        if vendor_id is None:
            raise ServiceError("Choose which vendor this login belongs to")
        if db.get(Vendor, vendor_id) is None:
            raise ServiceError("Vendor not found", 404)
    elif vendor_id is not None:
        raise ServiceError("Only vendor logins can be linked to a vendor")

    user = User(name=name.strip(), email=email, password_hash=hash_password(password), role=role, vendor_id=vendor_id)
    db.add(user)
    db.flush()
    return user
