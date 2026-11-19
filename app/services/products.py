"""Products: listing, adding, editing, soft delete, and the SKU upsert behind every import."""
import re
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.import_job import ImportJob
from app.models.product import Product, StockLocation
from app.schemas.product import ImportIssue, ProductCreate, ProductImportRow

AVAILABLE = "AVAILABLE"


def money(value: float | None) -> Decimal | None:
    """Prices live in the database as exact decimals. Converting here keeps floats out of the session (and out of the totals)."""
    return None if value is None else Decimal(str(round(value, 2)))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:56] or "sku"


def unique_id(db: Session, sku: str) -> str:
    """A product id made from its SKU ("DET-002" becomes "det-002"), numbered if that id is taken (deleted products keep theirs)."""
    base = slug(sku)
    candidate, n = base, 2
    while db.get(Product, candidate) is not None:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def list_products(db: Session) -> list[Product]:
    stmt = select(Product).where(Product.deleted_at.is_(None)).order_by(Product.created_at, Product.sku).options(selectinload(Product.locations))
    return list(db.scalars(stmt))


def get_product(db: Session, product_id: str, *, include_deleted: bool = False) -> Product:
    product = db.get(Product, product_id)
    if product is None or (product.deleted_at is not None and not include_deleted):
        raise ApiError(404, "Product not found.")
    return product


def find_by_sku(db: Session, sku: str) -> Product | None:
    return db.scalar(select(Product).where(func.lower(Product.sku) == sku.lower()))


def create_product(db: Session, data: ProductCreate) -> Product:
    if find_by_sku(db, data.sku) is not None:
        raise ApiError(409, f"A product with the SKU {data.sku} already exists.")
    fields = data.model_dump()
    fields["price"], fields["was"] = money(data.price), money(data.was)
    product = Product(id=unique_id(db, data.sku), **fields)
    db.add(product)
    db.commit()
    return product


def update_product(db: Session, product_id: str, changes: dict) -> Product:
    """`changes` holds only the fields the client sent. A null is allowed for the optional ones (it clears them)."""
    product = get_product(db, product_id)
    for required in ("name", "category", "channel", "price", "stock", "blurb"):
        if required in changes and changes[required] is None:
            raise ApiError(422, f"{required} cannot be cleared.")
    for key, value in changes.items():
        setattr(product, key, money(value) if key in ("price", "was") else value)
    db.commit()
    return product


def delete_product(db: Session, product_id: str) -> None:
    product = get_product(db, product_id)
    product.deleted_at = datetime.now(timezone.utc)
    db.commit()


def restore_product(db: Session, product_id: str) -> Product:
    product = get_product(db, product_id, include_deleted=True)
    product.deleted_at = None
    db.commit()
    return product


def _available(locations: list[StockLocation]) -> int:
    return sum(loc.quantity for loc in locations if loc.status.upper() == AVAILABLE)


def _apply_row(product: Product, row: ProductImportRow, *, is_new: bool) -> None:
    """Copy an import row onto a product. A blank description, size, logo or detail never wipes what is already there."""
    product.name = row.name
    product.category = row.category
    product.channel = row.channel
    product.price = money(row.price)
    product.was = money(row.was)
    if is_new or row.size is not None:
        product.size = row.size
    if is_new or row.blurb:
        product.blurb = row.blurb
    if is_new or row.image is not None:
        product.image = row.image
    for field in ("pid", "country", "business_group", "brand", "sub_brand", "segment", "form"):
        value = getattr(row, field)
        if is_new or value is not None:
            setattr(product, field, value)

    if row.locations is not None:
        # the sheet lists every stock location of this SKU: bring ours in line (update, add, and drop the ones it no longer lists)
        key = lambda system_id, location_id: (system_id.lower(), location_id.lower())  # noqa: E731
        ours = {key(l.system_id, l.location_id): l for l in product.locations}
        wanted = {key(l.system_id, l.location_id): l for l in row.locations}
        for place, loc in wanted.items():
            if place in ours:
                ours[place].quantity, ours[place].uom, ours[place].status = loc.quantity, loc.uom, loc.status
            else:
                product.locations.append(StockLocation(system_id=loc.system_id, location_id=loc.location_id, quantity=loc.quantity, uom=loc.uom, status=loc.status))
        for place, loc in ours.items():
            if place not in wanted:
                product.locations.remove(loc)
        product.stock = _available(product.locations)
    else:
        product.stock = row.stock


def classify(db: Session, rows: list[ProductImportRow]) -> tuple[int, int]:
    """How many of these SKUs would be added and how many would update an existing product."""
    if not rows:
        return 0, 0
    existing = {sku.lower() for sku in db.scalars(select(Product.sku).where(func.lower(Product.sku).in_([r.sku.lower() for r in rows])))}
    updates = sum(1 for r in rows if r.sku.lower() in existing)
    return len(rows) - updates, updates


def import_rows(
    db: Session, rows: list[ProductImportRow], *, employee_id: int | None, source: str, filename: str | None = None,
    issues: list[ImportIssue] | None = None, total_rows: int | None = None,
) -> tuple[int, int]:
    """Add new SKUs and update existing ones (matched by SKU, ignoring capitals). Nothing is ever deleted."""
    added = updated = 0
    for row in rows:
        product = find_by_sku(db, row.sku)
        if product is None:
            product = Product(id=unique_id(db, row.sku), sku=row.sku)
            _apply_row(product, row, is_new=True)
            db.add(product)
            db.flush()
            added += 1
        else:
            _apply_row(product, row, is_new=False)
            product.deleted_at = None  # importing a SKU that was deleted brings it back
            updated += 1
    db.add(ImportJob(
        employee_id=employee_id, source=source, filename=filename, total_rows=total_rows if total_rows is not None else len(rows),
        added=added, updated=updated, skipped=len(issues or []), issues=[i.model_dump() for i in (issues or [])],
    ))
    db.commit()
    return added, updated
