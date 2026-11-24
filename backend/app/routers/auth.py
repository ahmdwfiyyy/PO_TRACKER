from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.deps import DB, CurrentUser
from app.core.security import (
    clear_failures,
    create_token,
    hash_password,
    is_locked,
    record_failure,
    verify_password,
)
from app.models import User
from app.schemas.users import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut
from app.services.users import check_password_rules

router = APIRouter(prefix="/auth", tags=["auth"])


def to_user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.vendor_name = user.vendor.name if user.vendor else None
    return out


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: DB):
    if is_locked(body.email):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please wait 5 minutes and try again.")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        record_failure(body.email)
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated. Please contact Purchasing.")
    clear_failures(body.email)
    token = create_token(user.id, user.role, user.name, user.vendor_id)
    return LoginResponse(token=token, user=to_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return to_user_out(user)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordRequest, user: CurrentUser, db: DB):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Your current password is not correct")
    check_password_rules(body.new_password)
    user.password_hash = hash_password(body.new_password)
    db.commit()
