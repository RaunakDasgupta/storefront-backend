"""Orders. The server is the authority on prices and stock: what the browser sends is only used to know *which* products and how many."""
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ApiError
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.employee import Employee
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.order import Address, OrderCreate, OrderLineOut, OrderOut


def parse_code(code: str) -> int:
    """ORD_1002 -> 1002. Anything else is simply 'not found'."""
    match = re.fullmatch(r"ORD_(\d+)", code.strip(), flags=re.IGNORECASE)
    if not match:
        raise ApiError(404, "Order not found.")
    return int(match.group(1))


def to_out(order: Order) -> OrderOut:
    created = order.created_at if order.created_at.tzinfo else order.created_at.replace(tzinfo=timezone.utc)
    return OrderOut(
        id=order.code, date=created.astimezone(timezone.utc).date(), channel=order.channel, customer=UserOut(name=order.customer_name, email=order.customer_email),
        shipping=Address(full_name=order.ship_full_name, phone=order.ship_phone, line1=order.ship_line1, line2=order.ship_line2, city=order.ship_city, state=order.ship_state, pin=order.ship_pin),
        items=[OrderLineOut(id=i.product_id, name=i.name, size=i.size, qty=i.qty, price=float(i.unit_price)) for i in order.items],
        total=float(order.total), step=order.step,
    )


def list_orders(db: Session, user: User | Employee) -> list[Order]:
    """Customers get their own orders, admins get everyone's. Newest first."""
    stmt = select(Order).where(Order.deleted_at.is_(None)).options(selectinload(Order.items)).order_by(Order.id.desc())
    if not isinstance(user, Employee):  # staff see every order, a customer only their own
        stmt = stmt.where(Order.user_id == user.id)
    return list(db.scalars(stmt))


def _take_stock(product: Product, qty: int) -> None:
    """Remove `qty` from the product and, to keep the two in step, from its available stock locations (largest first)."""
    product.stock -= qty
    remaining = qty
    for loc in sorted((l for l in product.locations if l.status.upper() == "AVAILABLE"), key=lambda l: -l.quantity):
        used = min(loc.quantity, remaining)
        loc.quantity -= used
        remaining -= used
        if remaining == 0:
            break


def create_orders(db: Session, user: User, data: OrderCreate) -> list[Order]:
    # 1. what was asked for: product id -> quantity (the same product listed twice is added up)
    wanted: dict[str, int] = defaultdict(int)
    for group in data.groups:
        for line in group.items:
            wanted[line.id] += line.qty
    if not wanted:
        raise ApiError(422, "Your cart is empty.")

    # 2. the products, locked so two checkouts cannot both take the last unit
    stmt = select(Product).where(Product.id.in_(list(wanted)), Product.deleted_at.is_(None)).options(selectinload(Product.locations)).with_for_update()
    products = {p.id: p for p in db.scalars(stmt)}
    for product_id in wanted:
        if product_id not in products:
            raise ApiError(409, "One of the items in your cart is no longer available. Remove it and try again.")
    for product_id, qty in wanted.items():
        product = products[product_id]
        if product.stock < qty:
            raise ApiError(409, f"Only {product.stock} of {product.name} left." if product.stock else f"{product.name} is out of stock.")

    # 3. price it from our own catalog, one order per channel
    by_channel: dict[str, list[tuple[Product, int]]] = defaultdict(list)
    for product_id, qty in wanted.items():
        by_channel[products[product_id].channel].append((products[product_id], qty))
    totals = {channel: sum((p.price * qty for p, qty in lines), Decimal(0)) for channel, lines in by_channel.items()}
    grand_total = sum(totals.values(), Decimal(0))

    # 4. the payment must be this customer's, successful, unused, and for exactly this total
    payment = db.scalar(select(Payment).where(Payment.ref == data.payment_ref))
    if payment is None or payment.user_id != user.id or payment.status != "succeeded":
        raise ApiError(402, "We could not find a successful payment for this order. Pay again.")
    if db.scalar(select(Order.id).where(Order.payment_id == payment.id).limit(1)) is not None:
        raise ApiError(409, "This payment has already been used for an order.")
    if Decimal(payment.amount) != grand_total:
        raise ApiError(409, "The prices changed after you paid, so the amount no longer matches. Check your cart and pay again.")

    # 5. place the orders and take the stock
    made: list[Order] = []
    for channel in ("retail", "bulk"):
        if channel not in by_channel:
            continue
        order = Order(
            user_id=user.id, payment_id=payment.id, channel=channel, step=0, total=totals[channel],
            customer_name=user.name, customer_email=user.email,
            ship_full_name=data.shipping.full_name, ship_phone=data.shipping.phone, ship_line1=data.shipping.line1, ship_line2=data.shipping.line2,
            ship_city=data.shipping.city, ship_state=data.shipping.state, ship_pin=data.shipping.pin,
            created_at=datetime.now(timezone.utc),
        )
        for product, qty in by_channel[channel]:
            order.items.append(OrderItem(product_id=product.id, name=product.name, size=product.size, unit_price=product.price, qty=qty))
            _take_stock(product, qty)
        db.add(order)
        made.append(order)
    db.commit()
    return made


def _get(db: Session, code: str, *, include_deleted: bool = False) -> Order:
    order = db.scalar(select(Order).where(Order.id == parse_code(code)).options(selectinload(Order.items)))
    if order is None or (order.deleted_at is not None and not include_deleted):
        raise ApiError(404, "Order not found.")
    return order


def set_step(db: Session, code: str, step: int) -> Order:
    order = _get(db, code)
    order.step = step
    db.commit()
    return order


def delete_order(db: Session, code: str) -> None:
    """Hidden, not erased, so Undo works. The stock it took is not put back."""
    order = _get(db, code)
    order.deleted_at = datetime.now(timezone.utc)
    db.commit()


def restore_order(db: Session, code: str) -> Order:
    order = _get(db, code, include_deleted=True)
    order.deleted_at = None
    db.commit()
    return order
