"""User management (Purchasing only): vendor logins, receiving users, other purchasing users."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DB, PurchasingUser
from app.core.security import hash_password
from app.models import Role, User
from app.routers.auth import to_user_out
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services.users import check_password_rules, create_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: PurchasingUser, role: Role | None = None, vendor_id: int | None = None):
    query = select(User).options(selectinload(User.vendor)).order_by(User.role, User.name)
    if role:
        query = query.where(User.role == role)
    if vendor_id:
        query = query.where(User.vendor_id == vendor_id)
    return [to_user_out(u) for u in db.scalars(query)]


@router.post("", response_model=UserOut, status_code=201)
def add_user(body: UserCreate, db: DB, _: PurchasingUser):
    user = create_user(
        db, name=body.name, email=body.email, password=body.password, role=body.role, vendor_id=body.vendor_id
    )
    db.commit()
    return to_user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: DB, me: PurchasingUser):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.is_active is False and user.id == me.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if body.name is not None:
        user.name = body.name
    if body.is_active is not None:
        # Deactivating only blocks sign-in. Nothing is deleted, so a vendor's history stays intact.
        user.is_active = body.is_active
    if body.password:
        check_password_rules(body.password)
        user.password_hash = hash_password(body.password)
    db.commit()
    return to_user_out(user)
