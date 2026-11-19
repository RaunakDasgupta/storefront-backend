from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CUSTOMER = "customer"
ADMIN = "admin"


class User(Base):
    """Customers (storefront) and admins (admin portal) share one table; `role` tells them apart."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    # admins can also sign in with an employee ID such as EMP-1001
    employee_id: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16), default=CUSTOMER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # emails and employee IDs are unique regardless of capitals
        Index("uq_users_email_lower", func.lower(email), unique=True),
        Index("uq_users_employee_id_lower", func.lower(employee_id), unique=True),
    )
