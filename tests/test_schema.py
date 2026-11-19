"""create_schema builds an empty database and brings an older one up to date, with SQLAlchemy alone."""
from sqlalchemy import create_engine, inspect, text

from app.db.schema import create_schema, missing_columns, missing_tables


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
