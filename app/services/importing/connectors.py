"""Reading SKU rows straight from a database, for the admin portal's Import > PostgreSQL / SQLite / AWS RDS sources.

Real connections: PostgreSQL, SQLite (a file inside IMPORT_SQLITE_DIR) and AWS RDS for PostgreSQL.
Not enabled on this server (they answer 501 with a clear message): S3, Google Cloud Storage, Cloud SQL and BigQuery.

The table's columns are matched by name exactly like the columns of a spreadsheet (see catalog_sheet.py).
Every read is read-only, limited to one table and one more row than the import limit, and passwords never appear in messages.
"""
import re
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.errors import ApiError

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$")
_SSL_MODES = {"Require SSL": "require", "Prefer SSL": "prefer", "No SSL": "disable"}
NOT_ENABLED = {
    ("aws", "s3"): "Reading from S3",
    ("gcp", "gcs"): "Reading from Google Cloud Storage",
    ("gcp", "cloudsql"): "Reading from Cloud SQL",
    ("gcp", "bigquery"): "Reading from BigQuery",
}


def _setting(settings: dict[str, str], key: str, label: str) -> str:
    value = (settings.get(key) or "").strip()
    if not value:
        raise ApiError(422, f"Enter the {label}.")
    return value


def _quoted_table(engine: Engine, table: str) -> str:
    parts = table.split(".")
    if len(parts) > 2 or not all(_IDENTIFIER.match(p) for p in parts):
        raise ApiError(422, "The table name can only have letters, numbers and underscores, like products or public.products.")
    quote = engine.dialect.identifier_preparer.quote
    return ".".join(quote(p) for p in parts)


def _clean(message: str, settings: dict[str, str]) -> str:
    """A short, safe reason: the first line, with the password and the long driver details removed."""
    first = message.strip().splitlines()[0] if message.strip() else "unknown error"
    secret = settings.get("password") or settings.get("secretKey") or ""
    if secret:
        first = first.replace(secret, "***")
    return first[:200]


def _read(engine: Engine, table: str, settings: dict[str, str], max_rows: int) -> list[list[str]]:
    quoted = _quoted_table(engine, table)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {quoted} LIMIT :n"), {"n": max_rows + 1})  # noqa: S608  (the table name is validated and quoted)
            header = [str(c) for c in result.keys()]
            rows = [["" if v is None else str(v) for v in row] for row in result]
    except SQLAlchemyError as err:
        raise ApiError(400, f"Could not read {table}: {_clean(str(getattr(err, 'orig', err)), settings)}")
    finally:
        engine.dispose()
    return [header, *rows]


def _postgres(settings: dict[str, str]) -> list[list[str]]:
    try:
        port = int(settings.get("port") or 5432)
    except ValueError:
        raise ApiError(422, "Enter a port from 1 to 65535.")
    if not 1 <= port <= 65535:
        raise ApiError(422, "Enter a port from 1 to 65535.")
    url = URL.create(
        "postgresql+psycopg", username=_setting(settings, "user", "user"), password=settings.get("password") or None,
        host=_setting(settings, "host", "host"), port=port, database=_setting(settings, "database", "database"),
        query={"sslmode": _SSL_MODES.get(settings.get("ssl", ""), "prefer"), "connect_timeout": "8"},
    )
    table = settings.get("table", "").strip() or "products"
    engine = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=15000"})
    return _read(engine, table, settings, get_settings().max_import_rows)


def _sqlite(settings: dict[str, str]) -> list[list[str]]:
    base = Path(get_settings().import_sqlite_dir).resolve()
    name = _setting(settings, "file", "database file")
    path = (base / name).resolve() if not Path(name).is_absolute() else Path(name).resolve()
    if base != path and base not in path.parents:
        raise ApiError(422, f"SQLite files must be inside {base}. Copy the file there and use its name.")
    if not path.is_file():
        raise ApiError(422, f"There is no database file {name} in {base}.")
    table = settings.get("table", "").strip() or "products"
    # opened directly, not through a sqlite:/// URL: SQLAlchemy decodes %xx in URLs, which breaks Windows paths (C:\\Users\\...) and names with spaces, # or ?
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True))
    return _read(engine, table, settings, get_settings().max_import_rows)


def read_source(connector: str, service: str, settings: dict[str, str]) -> list[list[str]]:
    """The table as rows of text, header first, ready for `parse_sheet`."""
    if (connector, service) in NOT_ENABLED:
        raise ApiError(501, f"{NOT_ENABLED[(connector, service)]} is not enabled on this server. Use PostgreSQL, SQLite, RDS or a CSV/Excel file.")
    if connector == "postgres" or (connector == "aws" and service == "rds"):
        return _postgres(settings)
    if connector == "sqlite":
        return _sqlite(settings)
    raise ApiError(422, f"Unknown source: {connector}/{service}.")
