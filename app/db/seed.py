"""Demo data for a new database: the demo accounts, the sample catalog sheet and a week of orders.

Runs on start when SEED_DEMO_DATA=true, or by hand:  python -m app.db.seed
It only fills what is empty, so running it twice changes nothing.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.employee import Employee
from app.models.user import User
from app.schemas.order import Address, OrderCreate, OrderGroupIn, OrderLineIn
from app.services import orders as order_service
from app.services import products as product_service
from app.services.catalog_sheet import parse_sheet
from app.services.readers import read_upload

log = logging.getLogger("storefront.seed")
SAMPLE_SHEET = Path(__file__).resolve().parents[2] / "samples" / "Unilever_storefront_products.csv"

DEMO_CUSTOMER = {"name": "Alex Morgan", "email": "customer@storefront.test", "password": "customer123"}
DEMO_ADMIN = {"name": "Sam Rivera", "email": "admin@storefront.test", "employee_id": "EMP-1001", "password": "admin1234"}
OTHER_CUSTOMERS = [
    {"name": "Liam Chen", "email": "liam.chen@example.com"},
    {"name": "Sofia Rossi", "email": "sofia.rossi@example.com"},
    {"name": "Noah Williams", "email": "noah.williams@example.com"},
]

ADDRESSES = [
    Address(full_name="Alex Morgan", phone="9820011001", line1="12 MG Road", city="Pune", state="Maharashtra", pin="411001"),
    Address(full_name="Liam Chen", phone="9820011002", line1="48 Linking Road, Bandra West", city="Mumbai", state="Maharashtra", pin="400050"),
    Address(full_name="Sofia Rossi", phone="9820011003", line1="Plot 7, Peenya Industrial Area", city="Bengaluru", state="Karnataka", pin="560058"),
    Address(full_name="Noah Williams", phone="9820011004", line1="21 Connaught Place", city="Delhi", state="Delhi", pin="110001"),
]

# (customer index, [(SKU number, quantity)], address index, fulfilment step, days ago)
DEMO_ORDERS = [
    (1, [(10001, 2), (10018, 1)], 1, 3, 6),
    (2, [(10011, 3)], 2, 3, 5),
    (3, [(10016, 1), (10017, 2)], 3, 2, 4),
    (0, [(10006, 6), (10009, 4)], 0, 3, 3),
    (1, [(10014, 1), (10015, 1)], 1, 1, 2),
    (0, [(10002, 1), (10005, 1), (10007, 2)], 0, 1, 1),
    (2, [(10019, 2), (10020, 1)], 2, 0, 0),
    (0, [(10008, 2)], 0, 0, 0),
]


def _ensure_user(db: Session, *, name: str, email: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        user = User(name=name, email=email, password_hash=hash_password(password))
        db.add(user)
        db.flush()
    return user


def _ensure_employee(db: Session, *, name: str, email: str, employee_id: str, password: str) -> Employee:
    employee = db.scalar(select(Employee).where(func.lower(Employee.email) == email.lower()))
    if employee is None:
        employee = Employee(name=name, email=email, employee_id=employee_id, password_hash=hash_password(password))
        db.add(employee)
        db.flush()
    return employee


def _import_sample_catalog(db: Session) -> int:
    if not SAMPLE_SHEET.is_file():
        log.warning("Sample catalog %s not found, no products seeded.", SAMPLE_SHEET)
        return 0
    result = parse_sheet(read_upload(SAMPLE_SHEET.name, SAMPLE_SHEET.read_bytes()))
    added, _ = product_service.import_rows(db, result.rows, employee_id=None, source="csv", filename=SAMPLE_SHEET.name, issues=result.issues, total_rows=result.total_rows)
    return added


def _place_demo_orders(db: Session, customers: list[User]) -> int:
    placed = 0
    now = datetime.now(timezone.utc)
    for customer_index, lines, address_index, step, days_ago in DEMO_ORDERS:
        user = customers[customer_index]
        items, total = [], Decimal(0)
        for number, qty in lines:
            product = db.scalar(select(Product).where(Product.sku.like(f"{number}-%")))
            if product is None or product.stock < qty:
                break
            items.append(OrderLineIn(id=product.id, qty=qty))
            total += product.price * qty
        else:
            payment = Payment(ref=f"PAY_DEMO{placed:04d}", user_id=user.id, amount=total, currency="INR", status="succeeded", card_last4="4242")
            db.add(payment)
            db.commit()
            made = order_service.create_orders(
                db, user, OrderCreate(shipping=ADDRESSES[address_index], payment_ref=payment.ref, groups=[OrderGroupIn(channel="retail", items=items)]),
            )
            for order in made:
                order.step = step
                order.created_at = now - timedelta(days=days_ago, hours=placed)
            db.commit()
            placed += len(made)
    return placed


def seed_demo_data(db: Session) -> None:
    customer = _ensure_user(db, **DEMO_CUSTOMER)
    _ensure_employee(db, **DEMO_ADMIN)
    others = [_ensure_user(db, **c, password="customer123") for c in OTHER_CUSTOMERS]
    db.commit()

    if db.scalar(select(func.count()).select_from(Product)) == 0:
        log.info("Seeded %s products from %s", _import_sample_catalog(db), SAMPLE_SHEET.name)
    if db.scalar(select(func.count()).select_from(Order)) == 0:
        log.info("Seeded %s demo orders", _place_demo_orders(db, [customer, *others]))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        seed_demo_data(session)
    print("Demo data is in place.")
