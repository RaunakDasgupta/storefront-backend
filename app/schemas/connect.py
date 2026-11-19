from pydantic import Field

from app.schemas.common import CamelModel


class ConnectIn(CamelModel):
    """Which database to read the catalog from. `settings` are the fields of the admin portal's connection form."""

    connector: str = Field(description="postgres, sqlite, aws or gcp.", examples=["postgres"])
    service: str = Field(description="postgres, sqlite, s3 or rds (aws), gcs, cloudsql or bigquery (gcp).", examples=["postgres"])
    settings: dict[str, str] = Field(
        default_factory=dict,
        description="PostgreSQL / RDS: host, port, database, user, password, table, ssl. SQLite: file, table.",
        examples=[{"host": "db.example.com", "port": "5432", "database": "storefront", "user": "reader", "password": "secret", "table": "products", "ssl": "Prefer SSL"}],
    )
