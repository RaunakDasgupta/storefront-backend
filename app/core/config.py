"""Settings, read from environment variables or a `.env` file. See `.env.example`."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- database -------------------------------------------------------------------------------------------
    # Your Postgres, which can be on another machine: postgresql://user:password@HOST:5432/storefront
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/storefront"
    # Run `alembic upgrade head` when the API starts, so a new database is ready without any extra step.
    auto_migrate: bool = True
    # Fill an empty database with the demo accounts, products and orders (safe to leave on: it only seeds once).
    seed_demo_data: bool = True

    # --- api -------------------------------------------------------------------------------------------------
    api_prefix: str = "/api/v1"
    # Where the frontend runs. Comma separated. "*" allows any origin (fine for a demo, not for production).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- security --------------------------------------------------------------------------------------------
    secret_key: str = "change-me-before-sharing-this-server"
    access_token_minutes: int = 12 * 60

    # --- imports ---------------------------------------------------------------------------------------------
    # SQLite files for the "SQLite" import source must live inside this folder.
    import_sqlite_dir: str = "./data/import"
    max_import_rows: int = 1000
    max_upload_bytes: int = 5_000_000

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        """Accept the plain postgres:// and postgresql:// URLs that most tools print, and use the installed driver."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
