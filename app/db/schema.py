"""Creating and updating the database schema with SQLAlchemy alone (no migration tool).

`create_schema` runs when the API starts (AUTO_CREATE_SCHEMA=true) and does two things:

1. `Base.metadata.create_all`: every table that does not exist yet is created, with its indexes and constraints.
2. A small additive sync for tables that already exist: a column you added to a model is added to the table, and an index you
   added to a model is created.

That is everything it does. It never drops, renames or retypes anything and never touches data. Changes like those (and adding a
NOT NULL column to a table that already has rows) are done by hand in SQL: SQLAlchemy has no tool for them. Run it yourself with

    python -m app.db.schema            # create / update the tables
    python -m app.db.schema --check    # only report what is missing; exit 1 if anything is
"""
import logging
import sys

from sqlalchemy import Table, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.db.base import Base

log = logging.getLogger("storefront.schema")


def missing_columns(engine: Engine) -> list[tuple[Table, str]]:
    """(table, column name) for each model column that the existing table does not have yet."""
    inspector = inspect(engine)
    found = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        found += [(table, c.name) for c in table.columns if c.name not in have]
    return found


def missing_tables(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    return [t.name for t in Base.metadata.sorted_tables if not inspector.has_table(t.name)]


def _add_column(engine: Engine, table: Table, name: str) -> None:
    column = table.columns[name]
    ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
    if not column.nullable and column.server_default is None:
        # existing rows have no value for it, so it cannot be NOT NULL yet: add it as nullable and say so
        ddl = ddl.replace(" NOT NULL", "")
        log.warning("Added %s.%s as nullable: it has no server default. Fill it in and make it NOT NULL by hand.", table.name, name)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"ALTER TABLE {engine.dialect.identifier_preparer.format_table(table)} ADD COLUMN {ddl}")


def _index_names(engine: Engine, table: Table) -> set[str]:
    if engine.dialect.name == "sqlite":  # SQLite's reflection hides expression indexes such as lower(sku)
        with engine.connect() as conn:
            rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?", (table.name,))
            return {r[0] for r in rows}
    return {i["name"] for i in inspect(engine).get_indexes(table.name)}


def create_schema(engine: Engine) -> list[str]:
    """Bring the database in line with the models. Returns a description of what it changed (empty if nothing)."""
    changes = [f"created table {name}" for name in missing_tables(engine)]
    Base.metadata.create_all(engine)

    for table, name in missing_columns(engine):
        _add_column(engine, table, name)
        changes.append(f"added column {table.name}.{name}")

    # indexes added to a model after its table was created (create_all only makes indexes for new tables)
    for table in Base.metadata.sorted_tables:
        have = _index_names(engine, table)
        for index in table.indexes:
            if index.name not in have:
                index.create(engine)
                changes.append(f"created index {index.name}")
    for change in changes:
        log.info("Schema: %s", change)
    return changes


if __name__ == "__main__":
    from app.db.session import engine as app_engine

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if "--check" in sys.argv:
        problems = [f"missing table {t}" for t in missing_tables(app_engine)] + [f"missing column {t.name}.{c}" for t, c in missing_columns(app_engine)]
        print("\n".join(problems) if problems else "The database matches the models.")
        sys.exit(1 if problems else 0)
    done = create_schema(app_engine)
    print("\n".join(done) if done else "The database already matches the models.")
