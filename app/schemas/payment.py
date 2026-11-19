import re
from datetime import datetime, timezone

from pydantic import Field, field_validator, model_validator

from app.schemas.common import CamelModel


class Card(CamelModel):
    number: str = Field(description="The card number. Never stored: only the last 4 digits are kept.", examples=["4242 4242 4242 4242"])
    name: str = Field(min_length=1, max_length=120)
    expiry: str = Field(description="MM/YY", examples=["12/39"])
    cvc: str = Field(description="The 3 or 4 digit security code. Never stored.", examples=["123"])

    @field_validator("number")
    @classmethod
    def _number(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if not 12 <= len(digits) <= 19 or not luhn_ok(digits):
            raise ValueError("enter a valid card number")
        return digits

    @field_validator("expiry")
    @classmethod
    def _expiry(cls, v: str) -> str:
        m = re.fullmatch(r"\s*(\d{2})\s*/\s*(\d{2})\s*", v)
        if not m or not 1 <= int(m.group(1)) <= 12:
            raise ValueError("enter the expiry as MM/YY")
        month, year = int(m.group(1)), 2000 + int(m.group(2))
        now = datetime.now(timezone.utc)
        # a card works until the end of its expiry month
        if (year, month) < (now.year, now.month):
            raise ValueError("this card has expired")
        return v.strip()

    @field_validator("cvc")
    @classmethod
    def _cvc(cls, v: str) -> str:
        if not re.fullmatch(r"\d{3,4}", v):
            raise ValueError("enter the 3 or 4 digit security code")
        return v


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class ChargeIn(CamelModel):
    amount: float = Field(gt=0, le=10_000_000, description="The order total in rupees.", examples=[249])
    currency: str = Field("INR", pattern="^INR$")
    card: Card

    @model_validator(mode="after")
    def _round(self):
        self.amount = round(self.amount, 2)
        return self


class ChargeOut(CamelModel):
    ref: str = Field(examples=["PAY_1A2B3C4D"])
