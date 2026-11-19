import re
from datetime import date

from pydantic import Field, field_validator

from app.schemas.common import CamelModel
from app.schemas.auth import UserOut
from app.schemas.product import Channel


class Address(CamelModel):
    """Where an order is delivered."""

    full_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(max_length=30, description="A 10-digit mobile number, with or without +91.")
    line1: str = Field(min_length=1, max_length=200)
    line2: str = Field("", max_length=200)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=80)
    pin: str = Field(description="A 6-digit PIN code.")

    @field_validator("full_name", "line1", "city", "state")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if not (len(digits) == 10 or (len(digits) == 12 and digits.startswith("91"))):
            raise ValueError("enter a 10-digit mobile number")
        return v.strip()

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[1-9]\d{5}", v):
            raise ValueError("enter a 6-digit PIN code")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [{"fullName": "Alex Morgan", "phone": "9876543210", "line1": "12 MG Road", "line2": "", "city": "Pune", "state": "Maharashtra", "pin": "411001"}]
        }
    }


class OrderLineIn(CamelModel):
    id: str = Field(description="The product id.")
    qty: int = Field(ge=1, le=10_000)
    # the browser also sends what it showed; the server ignores it and uses its own prices
    name: str | None = Field(None, description="Ignored.")
    size: str | None = Field(None, description="Ignored.")
    price: float | None = Field(None, description="Ignored: the server prices the order from its own catalog.")


class OrderGroupIn(CamelModel):
    channel: Channel = Field(description="Ignored: items are grouped by their product's channel.")
    items: list[OrderLineIn] = Field(max_length=200)


class OrderCreate(CamelModel):
    """Place the cart. One order is created per channel (retail, bulk) that has items."""

    customer: dict | None = Field(None, description="Ignored: the order is placed for the signed-in customer.")
    shipping: Address
    payment_ref: str = Field(min_length=1, max_length=32, description="The `ref` returned by POST /payments for this total.")
    groups: list[OrderGroupIn] = Field(max_length=10)


class OrderLineOut(CamelModel):
    id: str
    name: str
    size: str | None = None
    qty: int
    price: float


class OrderOut(CamelModel):
    id: str = Field(description="The order number, like ORD_1002.")
    date: date
    channel: Channel
    customer: UserOut
    shipping: Address | None = None
    items: list[OrderLineOut]
    total: float
    step: int = Field(ge=0, le=3, description="0 Confirmed, 1 Preparing, 2 Packed, 3 Ready for dispatch.")


class StepUpdate(CamelModel):
    step: int = Field(ge=0, le=3, description="0 Confirmed, 1 Preparing, 2 Packed, 3 Ready for dispatch.")
