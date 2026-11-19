"""Reading the catalog sheet: the spreadsheet the business keeps (Unilever_storefront_products).

One row per SKU, or one row per SKU and stock location. Header names are case-insensitive and spaces, dashes and underscores
are interchangeable. Columns this module does not know (such as the stray AUTOSTORE / AS_BIN_A cells of the sample sheet) are ignored.

    Product columns   PID, Country, Business Group, Category, Brand, SubBrand, Segment, Form, SKU*, Current Sales Price*
                      (optional extras: Name, Size, Channel, Compare At Price, Description, Logo URL, Stock)
    Stock columns     system_id, location_id, quantity, uom, status

    * required
"""
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.schemas.product import ImportIssue, LocationRow, ProductImportRow, check_image

# the column names we understand, and the field each one fills
ALIASES: dict[str, str] = {
    "sku": "sku", "pid": "pid", "country": "country", "business_group": "business_group", "businessgroup": "business_group",
    "category": "category", "brand": "brand", "sub_brand": "sub_brand", "subbrand": "sub_brand", "segment": "segment", "form": "form",
    "current_sales_price": "price", "sales_price": "price", "price": "price",
    "name": "name", "size": "size", "channel": "channel", "type": "channel",
    "compare_at_price": "was", "compare_at": "was", "was": "was",
    "description": "blurb", "blurb": "blurb", "logo_url": "image", "logo": "image", "image_url": "image", "image": "image",
    "stock": "stock",
    "system_id": "system_id", "location_id": "location_id", "quantity": "quantity", "qty": "quantity", "uom": "uom", "status": "status",
}
REQUIRED = {"sku": "SKU", "price": "Current Sales Price"}
STOCK_COLUMNS = ("system_id", "location_id", "quantity", "uom", "status")
STATUSES = ("AVAILABLE", "BLOCKED", "DAMAGED", "HOLD", "QUARANTINE")

TEMPLATE_HEADER = [
    "PID", "Country", "Business Group", "Category", "Brand", "SubBrand", "Segment", "Form", "SKU", "Current Sales Price",
    "system_id", "location_id", "quantity", "uom", "status",
]

_PREFIX = re.compile(r"^\s*\d+\s*[-_:]\s*")
_SIZE_AT_END = re.compile(r"\s+(\d+(?:\.\d+)?\s?(?:ml|ltr|l|gm|g|kg|pcs|pc|pack|sheets|rolls))\s*$", re.IGNORECASE)


def normalise_header(cell: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(cell).strip().lower()).strip("_")
    return ALIASES.get(key, "")


@dataclass
class SheetResult:
    rows: list[ProductImportRow] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    fatal: str | None = None
    total_rows: int = 0  # data rows in the sheet (blank lines left out)
    skipped: int = 0


def derive_name_and_size(sku: str, name: str, size: str) -> tuple[str, str | None]:
    """'10014-Bru Gold 100g' becomes the name 'Bru Gold' and the size '100g' unless the sheet says otherwise."""
    if name:
        return name, size or None
    derived = _PREFIX.sub("", sku).strip() or sku
    if not size:
        found = _SIZE_AT_END.search(derived)
        if found:
            size = found.group(1).replace(" ", "")
            derived = derived[: found.start()].strip() or derived
    return derived, size or None


def _number(raw: str) -> float | None:
    try:
        value = float(re.sub(r"[₹,\s]", "", raw))
    except ValueError:
        return None
    return value if value == value and abs(value) != float("inf") else None


def parse_sheet(table: list[list[str]], max_rows: int = 1000) -> SheetResult:
    """Validate a sheet that has already been read into rows of text (see readers.py). Never raises: problems become issues."""
    result = SheetResult()
    if not table or not any(c.strip() for c in table[0]):
        result.fatal = "The file is empty."
        return result

    columns = [normalise_header(c) for c in table[0]]
    missing = [label for key, label in REQUIRED.items() if key not in columns]
    if missing:
        result.fatal = f"Missing required column{'s' if len(missing) > 1 else ''}: {', '.join(missing)}."
        return result

    body = table[1:]
    if len(body) > max_rows + 200 or sum(1 for r in body if any(c.strip() for c in r)) > max_rows:
        result.fatal = f"The file has more than {max_rows} rows. Split it and upload each part."
        return result

    has_stock_columns = any(c in columns for c in STOCK_COLUMNS)
    by_sku: dict[str, ProductImportRow] = {}
    order: list[str] = []

    for index, raw in enumerate(body):
        line = index + 2  # spreadsheet-style: the header is row 1
        if not any(c.strip() for c in raw):
            continue
        result.total_rows += 1
        cells = {columns[i]: raw[i].strip() for i in range(min(len(columns), len(raw))) if columns[i]}
        get = lambda key: cells.get(key, "")  # noqa: E731

        def fail(message: str) -> None:
            result.issues.append(ImportIssue(line=line, message=message))
            result.skipped += 1

        sku = get("sku")
        if not sku:
            fail("SKU is empty.")
            continue
        if len(sku) > 120:
            fail(f"{sku[:30]}...: SKU is longer than 120 characters.")
            continue

        # --- where the stock sits (optional) ---------------------------------------------------------------------
        location: LocationRow | None = None
        if any(get(c) for c in STOCK_COLUMNS):
            quantity_raw = get("quantity")
            quantity = 0 if quantity_raw == "" else _number(quantity_raw)
            if quantity is None or quantity != int(quantity) or quantity < 0:
                fail(f"{sku}: quantity must be a whole number, like 25.")
                continue
            status = (get("status") or "AVAILABLE").upper()
            if status not in STATUSES:
                fail(f"{sku}: status must be one of {', '.join(STATUSES)}.")
                continue
            uom = (get("uom") or "EA").upper()
            if len(uom) > 10 or len(get("system_id")) > 40 or len(get("location_id")) > 60:
                fail(f"{sku}: system_id, location_id or uom is too long.")
                continue
            location = LocationRow(system_id=get("system_id") or "DEFAULT", location_id=get("location_id") or "DEFAULT", quantity=int(quantity), uom=uom, status=status)

        # --- a SKU that appeared before: only another stock location is allowed ---------------------------------
        key = sku.lower()
        if key in by_sku:
            if location is None:
                fail(f"{sku}: duplicate SKU in this file, the first row was used.")
                continue
            existing = by_sku[key]
            places = {(loc.system_id.lower(), loc.location_id.lower()) for loc in existing.locations or []}
            if (location.system_id.lower(), location.location_id.lower()) in places:
                fail(f"{sku}: this location ({location.system_id} / {location.location_id}) is listed twice.")
                continue
            existing.locations = [*(existing.locations or []), location]
            existing.stock = _available(existing.locations)
            continue

        # --- the product itself --------------------------------------------------------------------------------
        price_raw = get("price")
        price = _number(price_raw) if price_raw else None
        if price is None or price < 0:
            fail(f"{sku}: current sales price must be a number, like 249.")
            continue

        name, size = derive_name_and_size(sku, get("name"), get("size"))
        if len(name) > 120:
            fail(f"{sku}: name is longer than 120 characters.")
            continue
        if size and len(size) > 60:
            fail(f"{sku}: size is longer than 60 characters.")
            continue

        was_raw = get("was")
        was = None
        if was_raw:
            was = _number(was_raw)
            if was is None or was < 0:
                fail(f"{sku}: compare at price must be a number.")
                continue
            if was <= price:
                was = None  # only a higher "was" price makes sense

        channel = get("channel").lower() or "retail"
        if channel not in ("retail", "bulk"):
            fail(f"{sku}: channel must be retail or bulk.")
            continue

        image = get("image")
        try:
            check_image(image or None)
        except ValueError:
            fail(f"{sku}: logo_url must be a full https link or a /products/ file.")
            continue

        blurb = get("blurb")
        if len(blurb) > 500:
            fail(f"{sku}: description is longer than 500 characters.")
            continue

        if location is None and not has_stock_columns:
            stock_raw = get("stock")
            stock = 0 if stock_raw == "" else _number(stock_raw)
            if stock is None or stock != int(stock) or stock < 0:
                fail(f"{sku}: stock must be a whole number, like 25.")
                continue
        else:
            stock = 0

        try:
            row = ProductImportRow(
                sku=sku, name=name, size=size, price=price, was=was, category=get("category") or "General", channel=channel, stock=int(stock),
                blurb=blurb, image=image or None, pid=get("pid") or None, country=get("country") or None, business_group=get("business_group") or None,
                brand=get("brand") or None, sub_brand=get("sub_brand") or None, segment=get("segment") or None, form=get("form") or None,
                locations=[location] if location else None,
            )
        except ValidationError as err:  # a field too long or otherwise out of range
            first = err.errors()[0]
            fail(f"{sku}: {'.'.join(str(p) for p in first['loc'])} {first['msg'].lower()}.")
            continue
        if row.locations:
            row.stock = _available(row.locations)
        by_sku[key] = row
        order.append(key)

    result.rows = [by_sku[k] for k in order]
    return result


def _available(locations: list[LocationRow]) -> int:
    """Only AVAILABLE stock can be sold."""
    return sum(loc.quantity for loc in locations if loc.status.upper() == "AVAILABLE")
