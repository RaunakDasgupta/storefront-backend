from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# the `role` inside a login token: it says which table the token's id belongs to
CUSTOMER = "customer"
ADMIN = "admin"


class User(Base):
    """A storefront customer. Staff are in the separate `employees` table (app/models/employee.py)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # emails are unique regardless of capitals
    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)
