from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

RETAIL = "retail"
BULK = "bulk"


class Product(Base):
    """One sellable SKU. The columns after `image` come from the catalog sheet (Brand, SubBrand, Segment...)."""

    __tablename__ = "products"

    # a readable id made from the SKU ("10001-dove-intense-repair"): it is what the storefront puts in its URLs
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sku: Mapped[str] = mapped_column(String(120))
    pid: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(60))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    was: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # the "compare at" price shown struck through
    category: Mapped[str] = mapped_column(String(60), index=True)
    blurb: Mapped[str] = mapped_column(Text, default="", server_default="")
    # what can be sold now: the available quantity across the product's stock locations
    stock: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    channel: Mapped[str] = mapped_column(String(10), default=RETAIL, server_default=RETAIL)
    image: Mapped[str | None] = mapped_column(String(500))

    country: Mapped[str | None] = mapped_column(String(60))
    business_group: Mapped[str | None] = mapped_column(String(80))
    brand: Mapped[str | None] = mapped_column(String(80))
    sub_brand: Mapped[str | None] = mapped_column(String(80))
    segment: Mapped[str | None] = mapped_column(String(80))
    form: Mapped[str | None] = mapped_column(String(40))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # a deleted product is hidden, not erased, so the storefront's Undo works and old orders keep their items
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    locations: Mapped[list["StockLocation"]] = relationship(back_populates="product", cascade="all, delete-orphan", order_by="StockLocation.id")

    __table_args__ = (
        Index("uq_products_sku_lower", func.lower(sku), unique=True),
        CheckConstraint("price >= 0", name="price_not_negative"),
        CheckConstraint("stock >= 0", name="stock_not_negative"),
        CheckConstraint("channel IN ('retail', 'bulk')", name="channel_valid"),
    )


class StockLocation(Base):
    """Where a product's stock sits: the system_id, location_id, quantity, uom and status columns of the catalog sheet."""

    __tablename__ = "stock_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    system_id: Mapped[str] = mapped_column(String(40), default="DEFAULT")  # for example AUTOSTORE
    location_id: Mapped[str] = mapped_column(String(60), default="DEFAULT")  # for example AS_BIN_A
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    uom: Mapped[str] = mapped_column(String(10), default="EA")  # unit of measure; EA is "each"
    status: Mapped[str] = mapped_column(String(20), default="AVAILABLE")

    product: Mapped[Product] = relationship(back_populates="locations")

    __table_args__ = (
        UniqueConstraint("product_id", "system_id", "location_id", name="uq_stock_locations_place"),
        CheckConstraint("quantity >= 0", name="quantity_not_negative"),
    )
