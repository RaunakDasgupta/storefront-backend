from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# the four fulfilment steps; the storefront shows them as Confirmed, Preparing, Packed, Ready for dispatch
STEPS = ("Confirmed", "Preparing", "Packed", "Ready for dispatch")


class Order(Base):
    """One order. Retail and bulk items are fulfilled separately, so a checkout can create two of these."""

    __tablename__ = "orders"

    # the visible order number is ORD_ + this id (1001 and up), see `code`
    id: Mapped[int] = mapped_column(Integer, Identity(start=1001), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    step: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    # who ordered, as of the order (the account's name can change later)
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(254))

    # where it is going
    ship_full_name: Mapped[str] = mapped_column(String(120))
    ship_phone: Mapped[str] = mapped_column(String(30))
    ship_line1: Mapped[str] = mapped_column(String(200))
    ship_line2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    ship_city: Mapped[str] = mapped_column(String(80), index=True)
    ship_state: Mapped[str] = mapped_column(String(80), index=True)
    ship_pin: Mapped[str] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id")

    __table_args__ = (
        CheckConstraint("step BETWEEN 0 AND 3", name="step_valid"),
        CheckConstraint("channel IN ('retail', 'bulk')", name="channel_valid"),
        CheckConstraint("total >= 0", name="total_not_negative"),
    )

    @property
    def code(self) -> str:
        return f"ORD_{self.id:04d}"


class OrderItem(Base):
    """A line of an order. Name, size and price are copied from the product at the time, so later edits do not change old orders."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(60))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    qty: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (CheckConstraint("qty >= 1", name="qty_positive"),)
