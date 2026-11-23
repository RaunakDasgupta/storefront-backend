"""create_schema builds an empty database and brings an older one up to date, with SQLAlchemy alone."""
import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.db.schema import create_schema, database_encoding, missing_columns, missing_tables


def test_creates_everything_then_does_nothing(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    first = create_schema(engine)
    assert "created table users" in first
    assert not missing_tables(engine) and not missing_columns(engine)
    assert create_schema(engine) == []


def test_adds_columns_and_indexes_missing_from_an_old_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    create_schema(engine)
    with engine.begin() as conn:  # make it look like a table made before those were added
        conn.execute(text("DROP INDEX uq_products_sku_lower"))
        conn.execute(text("ALTER TABLE products DROP COLUMN brand"))
    assert [(t.name, c) for t, c in missing_columns(engine)] == [("products", "brand")]

    changes = create_schema(engine)

    assert "added column products.brand" in changes
    assert "created index uq_products_sku_lower" in changes
    assert {c["name"] for c in inspect(engine).get_columns("products")} >= {"brand"}
    assert create_schema(engine) == []


def test_the_database_encoding_is_reported_for_postgres_only(tmp_path):
    assert database_encoding(create_engine(f"sqlite:///{tmp_path / 'e.db'}")) is None


@pytest.mark.skipif(not os.environ["DATABASE_URL"].startswith("postgresql"), reason="needs Postgres (TEST_WITH_POSTGRES=1)")
def test_a_non_utf8_postgres_database_is_detected():
    url = make_url(os.environ["DATABASE_URL"])
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS latin1_check"))
        conn.execute(text("CREATE DATABASE latin1_check ENCODING 'LATIN1' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'"))
    try:
        latin = create_engine(url.set(database="latin1_check"))
        assert database_encoding(latin) == "LATIN1"
        assert database_encoding(admin) == "UTF8"
        latin.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS latin1_check"))
        admin.dispose()
