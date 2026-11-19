from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Employee(Base):
    """A member of staff who signs in to the admin portal. Separate from `users` (customers): own ids, own logins."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    employee_id: Mapped[str] = mapped_column(String(40))  # the badge number, such as EMP-1001; can be used to sign in
    password_hash: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # emails and employee IDs are unique regardless of capitals
        Index("uq_employees_email_lower", func.lower(email), unique=True),
        Index("uq_employees_employee_id_lower", func.lower(employee_id), unique=True),
    )
