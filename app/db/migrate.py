"""Run the database migrations from code (the API does this on start) or from the command line:

    python -m app.db.migrate            # upgrade to the latest schema
    python -m app.db.migrate --check    # exit 1 if the models and the migrations disagree
"""
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")


def check() -> None:
    command.check(alembic_config())


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
        print("The models and the migrations agree.")
    else:
        upgrade_to_head()
        print("The database is up to date.")
