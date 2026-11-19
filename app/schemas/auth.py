import re

from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import CamelModel

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserOut(CamelModel):
    name: str
    email: str


class UserRow(CamelModel):
    """One customer in the admin's list. Never includes the password hash."""

    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime


class EmployeeRow(UserRow):
    """One member of staff: a customer's fields plus the badge number (the `id` is the employees table's own)."""

    employee_id: str


class SessionOut(CamelModel):
    """What signing in returns. Send `token` as `Authorization: Bearer <token>` on later requests."""

    user: UserOut
    token: str

    model_config = {
        "json_schema_extra": {"examples": [{"user": {"name": "Alex Morgan", "email": "customer@storefront.test"}, "token": "eyJhbGciOiJIUzI1NiIs..."}]}
    }


class LoginIn(CamelModel):
    email: str = Field(max_length=254, examples=["customer@storefront.test"])
    password: str = Field(max_length=200, examples=["customer123"])


class RegisterIn(CamelModel):
    name: str = Field(min_length=1, max_length=120, examples=["Pat Lee"])
    email: str = Field(max_length=254, examples=["pat@example.com"])
    password: str = Field(min_length=8, max_length=200, examples=["a-long-password"])

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Enter your name.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("Enter a valid email address.")
        return v


class AdminLoginIn(CamelModel):
    identity: str = Field(max_length=254, description="Work email or employee ID.", examples=["admin@storefront.test", "EMP-1001"])
    password: str = Field(max_length=200, examples=["admin1234"])
