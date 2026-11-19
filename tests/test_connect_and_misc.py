import sqlite3
from pathlib import Path

from app.core.config import get_settings
from tests.conftest import API


def make_db(name: str, rows: list[tuple]) -> Path:
    path = Path(get_settings().import_sqlite_dir) / name
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE products ("SKU" TEXT, "Current Sales Price" REAL, "Brand" TEXT, quantity INTEGER)')
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", rows)
    con.commit()
    con.close()
    return path


def connect(client, admin, connector, service, **settings):
    return client.post(f"{API}/import/connect", headers=admin, json={"connector": connector, "service": service, "settings": settings})


def test_a_sqlite_table_is_read_like_a_spreadsheet(client, admin):
    make_db("catalog.sqlite", [("10-Dove Soap 100g", 31.5, "Dove", 12), ("11-Lux Soap 100g", 30, "Lux", None)])
    body = connect(client, admin, "sqlite", "sqlite", file="catalog.sqlite", table="products").json()
    assert [(r["name"], r["size"], r["price"], r["brand"], r["stock"]) for r in body["rows"]] == [("Dove Soap", "100g", 31.5, "Dove", 12), ("Lux Soap", "100g", 30, "Lux", 0)]
    # a quantity without a system_id / location_id goes into a DEFAULT location
    assert body["rows"][0]["locations"][0]["locationId"] == "DEFAULT"


def test_connections_are_limited_and_errors_are_friendly(client, admin, customer):
    assert connect(client, admin, "sqlite", "sqlite", file="missing.sqlite").status_code == 422
    assert "must be inside" in connect(client, admin, "sqlite", "sqlite", file="/etc/passwd").json()["message"]
    make_db("a.sqlite", [])
    assert connect(client, admin, "sqlite", "sqlite", file="a.sqlite", table="products; DROP TABLE products").status_code == 422
    assert "Could not read" in connect(client, admin, "sqlite", "sqlite", file="a.sqlite", table="nope").json()["message"]
    unreachable = connect(client, admin, "postgres", "postgres", host="127.0.0.1", port="1", database="d", user="u", password="hunter2")
    assert unreachable.status_code == 400 and "hunter2" not in unreachable.text
    assert connect(client, admin, "aws", "s3", bucket="b").status_code == 501
    assert connect(client, admin, "gcp", "bigquery").status_code == 501
    assert connect(client, admin, "nonsense", "x").status_code == 422
    assert client.post(f"{API}/import/connect", headers=customer, json={"connector": "sqlite", "service": "sqlite", "settings": {}}).status_code == 403


def test_health_and_error_shape(client):
    assert client.get(f"{API}/health").json() == {"status": "ok", "database": "up"}
    assert client.get("/", follow_redirects=False).headers["location"] == "/docs"
    missing = client.get(f"{API}/products/none")
    assert missing.status_code == 404 and missing.json() == {"message": "Product not found."}
    assert client.post(f"{API}/auth/login", json={}).json()["message"].startswith("Check the request:")


def test_swagger_documents_every_route():
    from app.main import app

    spec = app.openapi()
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            assert op.get("summary"), f"{method} {path} has no summary"
            assert op.get("tags"), f"{method} {path} has no tag"
