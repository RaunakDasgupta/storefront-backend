from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# from app.api.deps import require_customer
from app.api.deps import acting_as
from app.core.errors import COMMON_ERRORS, ErrorResponse
from app.db.session import get_db
from app.models.user import CUSTOMER, User
from app.schemas.payment import ChargeIn, ChargeOut
from app.services import payments as service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "", response_model=ChargeOut, summary="Pay (dummy gateway)",
    description=(
        "A dummy card gateway for the demo: **no money moves**. `4242 4242 4242 4242` is approved, `4000 0000 0000 0002` is declined and "
        "`4000 0000 0000 9995` has insufficient funds, each with any future expiry and any security code. The card number and security code are "
        "never stored (only the last 4 digits). Send the returned `ref` to `POST /orders`."
    ),
    responses={402: {"model": ErrorResponse, "description": "The card was declined."}, 422: COMMON_ERRORS[422]},
)
def pay(
    data: ChargeIn,
    db: Session = Depends(get_db),
    user: User = Depends(acting_as(CUSTOMER)),  # auth disabled, was Depends(require_customer)
) -> ChargeOut:
    return ChargeOut(ref=service.charge(db, user, data))
