"""Test setup. By default the tests run on a temporary SQLite file; set TEST_WITH_POSTGRES=1 to run them on a real (embedded)
Postgres instead, or TEST_DATABASE_URL to use a Postgres you already have. The database is built by the app itself on start
(SQLAlchemy create_all), so the tests exercise the same schema you deploy."""
import atexit
import os
import tempfile
from pathlib import Path

_workdir = Path(tempfile.mkdtemp(prefix="storefront-tests-"))


def _database_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    if os.environ.get("TEST_WITH_POSTGRES") == "1":
        import pgserver

        server = pgserver.get_server(_workdir / "pg", cleanup_mode="stop")
        atexit.register(server.cleanup)
        return server.get_uri()
    return f"sqlite:///{_workdir / 'test.db'}"


# the app reads its settings when it is imported, so they must be set first
os.environ["DATABASE_URL"] = _database_url()
os.environ["AUTO_CREATE_SCHEMA"] = "true"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["SECRET_KEY"] = "test-secret-that-is-long-enough-for-hs256"
os.environ["IMPORT_SQLITE_DIR"] = str(_workdir / "import")
(_workdir / "import").mkdir()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # starting the app creates the tables
        yield c


@pytest.fixture(autouse=True)
def clean_database(client):
    """Every test starts from empty tables."""
    yield
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()


def _make_user(email: str, role: str, password: str, name: str, employee_id: str | None = None):
    with SessionLocal() as db:
        db.add(User(name=name, email=email, employee_id=employee_id, password_hash=hash_password(password), role=role))
        db.commit()


@pytest.fixture
def customer(client):
    _make_user("pat@example.com", "customer", "pat-password", "Pat Lee")
    token = client.post(f"{API}/auth/login", json={"email": "pat@example.com", "password": "pat-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_customer(client):
    _make_user("sam@example.com", "customer", "sam-password", "Sam Roy")
    token = client.post(f"{API}/auth/login", json={"email": "sam@example.com", "password": "sam-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    _make_user("boss@example.com", "admin", "boss-password", "Boss Admin", employee_id="EMP-9")
    token = client.post(f"{API}/admin/auth/login", json={"identity": "EMP-9", "password": "boss-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def sheet(*rows: str) -> bytes:
    """A catalog sheet as CSV bytes, with the standard header."""
    header = "PID,Country,Business Group,Category,Brand,SubBrand,Segment,Form,SKU,Current Sales Price,system_id,location_id,quantity,uom,status"
    return ("\n".join([header, *rows]) + "\n").encode()
