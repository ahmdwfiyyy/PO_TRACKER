from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.models import Role
from app.schemas.common import ORM, Name


def _lower(v: str) -> str:
    return v.strip().lower()


Email = Annotated[EmailStr, AfterValidator(_lower)]


# --------------------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    email: Annotated[str, AfterValidator(_lower)]
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: Role
    vendor_id: int | None
    vendor_name: str | None = None
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    token: str
    user: UserOut


# --------------------------------------------------------------------------- user management (purchasing)
class UserCreate(BaseModel):
    name: Name
    email: Email
    password: str
    role: Role
    vendor_id: int | None = None


class UserUpdate(BaseModel):
    name: Name | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, description="Set to reset the user's password")


# --------------------------------------------------------------------------- vendors
class VendorIn(BaseModel):
    name: Name
    contact_person: Annotated[str | None, Field(max_length=200)] = None
    email: Email | None = None
    phone: Annotated[str | None, Field(max_length=50)] = None


class VendorUpdate(BaseModel):
    name: Name | None = None
    contact_person: Annotated[str | None, Field(max_length=200)] = None
    email: Email | None = None
    phone: Annotated[str | None, Field(max_length=50)] = None


class VendorOut(ORM):
    id: int
    name: str
    contact_person: str | None
    email: str | None
    phone: str | None
    created_at: datetime
    user_count: int = 0
    po_count: int = 0
    open_po_count: int = 0
