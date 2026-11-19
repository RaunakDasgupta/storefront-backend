from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import CamelModel

Channel = Literal["retail", "bulk"]


class ProductOut(CamelModel):
    """A product as the storefront and the admin portal read it. Empty fields are left out of the JSON."""

    id: str
    sku: str
    name: str
    size: str | None = None
    price: float
    was: float | None = Field(None, description="The 'compare at' price shown struck through.")
    category: str
    blurb: str = ""
    stock: int = Field(description="Units that can be sold now (available quantity across stock locations).")
    channel: Channel
    image: str | None = None
    pid: str | None = None
    country: str | None = None
    business_group: str | None = None
    brand: str | None = None
    sub_brand: str | None = None
    segment: str | None = None
    form: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "id": "10001-dove-intense-repair-shampoo-180ml", "sku": "10001-Dove Intense Repair Shampoo 180ml", "name": "Dove Intense Repair Shampoo",
                "size": "180ml", "price": 230, "category": "SHAMPOO", "blurb": "", "stock": 120, "channel": "retail", "pid": "10001-Dove Intense Repair Shampoo 180ml",
                "country": "India", "businessGroup": "Beauty & Well being", "brand": "Dove", "subBrand": "Intense Repair", "segment": "ALL OTHER", "form": "Liquid",
            }]
        }
    }


class ProductFields(CamelModel):
    """The fields the admin 'Add product' and 'Edit product' forms share."""

    name: str = Field(min_length=1, max_length=120)
    size: str | None = Field(None, max_length=60)
    category: str = Field(min_length=1, max_length=60)
    channel: Channel = "retail"
    price: float = Field(ge=0, le=10_000_000)
    was: float | None = Field(None, ge=0, le=10_000_000)
    stock: int = Field(0, ge=0, le=10_000_000)
    blurb: str = Field("", max_length=500)
    image: str | None = Field(None, max_length=500, description="An http(s) link, or a /products/... file the storefront serves.")

    @field_validator("name", "category")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("image")
    @classmethod
    def _safe_image(cls, v: str | None) -> str | None:
        return check_image(v)


def check_image(v: str | None) -> str | None:
    """Only http(s) links and the storefront's own /products/ files: never javascript: or data: URLs."""
    if v is None or v == "":
        return None
    v = v.strip()
    if v.startswith("/products/") and all(c.isalnum() or c in "._-" for c in v[len("/products/"):]) and len(v) > len("/products/"):
        return v
    if v.lower().startswith(("https://", "http://")) and " " not in v:
        return v
    raise ValueError("use a full https link or a /products/ file")


class ProductCreate(ProductFields):
    sku: str = Field(min_length=1, max_length=120, description="Unique, regardless of capitals.", examples=["DET-002"])
    pid: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=60)
    business_group: str | None = Field(None, max_length=80)
    brand: str | None = Field(None, max_length=80)
    sub_brand: str | None = Field(None, max_length=80)
    segment: str | None = Field(None, max_length=80)
    form: str | None = Field(None, max_length=40)

    @field_validator("sku")
    @classmethod
    def _sku(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ProductUpdate(CamelModel):
    """Only the fields you send change. Send `null` for `size`, `was` or `image` to clear them. The SKU never changes."""

    name: str | None = Field(None, min_length=1, max_length=120)
    size: str | None = Field(None, max_length=60)
    category: str | None = Field(None, min_length=1, max_length=60)
    channel: Channel | None = None
    price: float | None = Field(None, ge=0, le=10_000_000)
    was: float | None = Field(None, ge=0, le=10_000_000)
    stock: int | None = Field(None, ge=0, le=10_000_000)
    blurb: str | None = Field(None, max_length=500)
    image: str | None = Field(None, max_length=500)

    @field_validator("image")
    @classmethod
    def _safe_image(cls, v: str | None) -> str | None:
        return check_image(v)


class LocationRow(CamelModel):
    """One stock location of a SKU: the system_id, location_id, quantity, uom and status columns of the catalog sheet."""

    system_id: str = Field("DEFAULT", max_length=40, examples=["AUTOSTORE"])
    location_id: str = Field("DEFAULT", max_length=60, examples=["AS_BIN_A"])
    quantity: int = Field(0, ge=0, le=100_000_000)
    uom: str = Field("EA", max_length=10, description="Unit of measure. EA is 'each'.")
    status: str = Field("AVAILABLE", max_length=20, description="Only AVAILABLE stock can be sold.")


class ProductImportRow(ProductFields):
    """One SKU of an import, after validation. This is also what you POST to /products/import."""

    sku: str = Field(min_length=1, max_length=120)
    pid: str | None = Field(None, max_length=120)
    country: str | None = Field(None, max_length=60)
    business_group: str | None = Field(None, max_length=80)
    brand: str | None = Field(None, max_length=80)
    sub_brand: str | None = Field(None, max_length=80)
    segment: str | None = Field(None, max_length=80)
    form: str | None = Field(None, max_length=40)
    locations: list[LocationRow] | None = Field(None, description="When given, replaces the SKU's stock locations and `stock` is the available total.")

    @field_validator("sku")
    @classmethod
    def _sku(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ImportRequest(CamelModel):
    rows: list[ProductImportRow] = Field(max_length=1000)


class ImportResult(CamelModel):
    added: int
    updated: int


class ImportIssue(CamelModel):
    line: int = Field(description="Spreadsheet row number: the header is row 1.")
    message: str


class ImportSummary(CamelModel):
    total_rows: int = Field(description="Data rows in the file.")
    valid: int = Field(description="SKUs that passed validation.")
    new: int = Field(description="SKUs that would be added.")
    updates: int = Field(description="SKUs that already exist and would be updated.")
    skipped: int = Field(description="Rows left out because of a problem.")


class ImportValidation(CamelModel):
    """The result of checking a file (or a database table). `rows` is ready to POST to /products/import."""

    rows: list[ProductImportRow]
    issues: list[ImportIssue]
    fatal: str | None = Field(None, description="Set when the whole file is unusable (empty, wrong format, missing required columns).")
    summary: ImportSummary
