from sqlalchemy import func, select

from app.db.seed import seed_demo_data
from app.db.session import SessionLocal
from app.models import ImportJob, Order, Product, StockLocation, User
from tests.conftest import API


def counts(db):
    return {m.__name__: db.scalar(select(func.count()).select_from(m)) for m in (User, Product, StockLocation, Order, ImportJob)}


def test_the_demo_data_is_seeded_once_and_the_demo_logins_work(client):
    with SessionLocal() as db:
        seed_demo_data(db)
        first = counts(db)
        seed_demo_data(db)  # a second run changes nothing
        assert counts(db) == first
    assert first["User"] == 5 and first["Product"] == 40 and first["StockLocation"] == 44 and first["Order"] == 8 and first["ImportJob"] == 1

    assert client.post(f"{API}/auth/login", json={"email": "customer@storefront.test", "password": "customer123"}).status_code == 200
    token = client.post(f"{API}/admin/auth/login", json={"identity": "EMP-1001", "password": "admin1234"}).json()["token"]
    orders = client.get(f"{API}/orders", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(orders) == 8 and orders[0]["id"] > orders[-1]["id"]
    assert {o["shipping"]["city"] for o in orders} >= {"Pune", "Mumbai", "Bengaluru", "Delhi"}
    product = next(p for p in client.get(f"{API}/products").json() if p["sku"].startswith("10001-"))
    assert product["name"] == "Dove Intense Repair Shampoo" and product["brand"] == "Dove" and product["businessGroup"] == "Beauty & Well being"
    assert product["image"] == "/products/shampoo.jpg"
