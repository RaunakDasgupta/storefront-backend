from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

# from app.api.deps import current_user, require_admin, require_customer
from app.api.deps import acting_as
from app.core.errors import COMMON_ERRORS, ErrorResponse
from app.db.session import get_db
from app.models.user import ADMIN, CUSTOMER, User
from app.schemas.order import OrderCreate, OrderOut, StepUpdate
from app.services import orders as service

router = APIRouter(prefix="/orders", tags=["Orders"])
AUTH_ERRORS = {k: COMMON_ERRORS[k] for k in (422,)}  # was (401, 403, 422) while auth was on
NOT_FOUND = {404: {"model": ErrorResponse, "description": "No order with this number."}}


@router.get(
    "", response_model=list[OrderOut], response_model_exclude_none=True, summary="List orders",
    description="A customer gets their own orders, an admin gets everyone's. Newest first. Deleted orders are left out.",
)
def list_orders(
    db: Session = Depends(get_db),
    user: User = Depends(acting_as(ADMIN, any_role=True)),  # auth disabled, was Depends(current_user)
):
    return [service.to_out(o) for o in service.list_orders(db, user)]


@router.post(
    "", response_model=list[OrderOut], response_model_exclude_none=True, status_code=201, summary="Place an order (checkout)",
    description=(
        "Creates one order per channel (retail, bulk) that has items. **The server prices the order itself** from its catalog and checks stock; "
        "the names and prices in the request are ignored. `paymentRef` must be a successful payment of this customer (`POST /payments`) for exactly "
        "the total, and can only be used once. Stock is taken from the products."
    ),
    responses=AUTH_ERRORS | {
        402: {"model": ErrorResponse, "description": "No successful payment found for this customer and reference."},
        409: {"model": ErrorResponse, "description": "An item is out of stock or gone, the payment was already used, or the total changed since the payment."},
    },
)
def create_orders(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(acting_as(CUSTOMER)),  # auth disabled, was Depends(require_customer)
):
    return [service.to_out(o) for o in service.create_orders(db, user, data)]


@router.patch(
    "/{order_id}", response_model=OrderOut, response_model_exclude_none=True, summary="Change an order's status",
    description="Admin: moves the order to a fulfilment step (0 Confirmed, 1 Preparing, 2 Packed, 3 Ready for dispatch). The customer sees it on their next load.",
    responses=AUTH_ERRORS | NOT_FOUND,
)
def set_order_step(
    order_id: str,
    data: StepUpdate,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return service.to_out(service.set_step(db, order_id, data.step))


@router.delete(
    "/{order_id}", status_code=204, summary="Delete an order",
    description="Admin. A soft delete: it disappears from the admin portal and from the customer's My orders, and `/restore` (Undo) brings it back. The stock is not put back.",
    responses=AUTH_ERRORS | NOT_FOUND,
)
def delete_order(
    order_id: str,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
) -> Response:
    service.delete_order(db, order_id)
    return Response(status_code=204)


@router.post("/{order_id}/restore", response_model=OrderOut, response_model_exclude_none=True, summary="Undo a delete", responses=AUTH_ERRORS | NOT_FOUND)
def restore_order(
    order_id: str,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return service.to_out(service.restore_order(db, order_id))
