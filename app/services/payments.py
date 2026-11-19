"""The dummy payment gateway. It checks the card and records the charge; no money moves.

Test cards: 4242 4242 4242 4242 is approved, 4000 0000 0000 0002 is declined, 4000 0000 0000 9995 has insufficient funds.
Only the last 4 digits are kept: the full number and the security code are dropped as soon as the request ends.
"""
import secrets
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import ChargeIn

DECLINES = {
    "4000000000000002": "Your card was declined. Try a different card.",
    "4000000000009995": "Your card has insufficient funds. Try a different card.",
}


def charge(db: Session, user: User, data: ChargeIn) -> str:
    """Returns the payment reference, or raises 402 with the reason when the card is declined."""
    declined = DECLINES.get(data.card.number)
    payment = Payment(
        ref=f"PAY_{secrets.token_hex(4).upper()}", user_id=user.id, amount=Decimal(str(data.amount)), currency=data.currency,
        status="declined" if declined else "succeeded", card_last4=data.card.number[-4:], failure_reason=declined,
    )
    db.add(payment)
    db.commit()  # keep the record of a declined charge, even though we are about to answer with an error
    if declined:
        raise ApiError(402, declined)
    return payment.ref
