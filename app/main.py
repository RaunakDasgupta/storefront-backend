"""The FastAPI app: `uvicorn app.main:app`."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.db.schema import create_schema
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine

log = logging.getLogger("storefront")

DESCRIPTION = "The API behind Everyday Market. Log in, then press **Authorize** and paste the token."

TAGS = [{"name": n} for n in ("Health", "Customer auth", "Admin auth", "Users", "Products", "Orders", "Payments", "Import sources")]


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    try:
        if settings.auto_create_schema:
            create_schema(engine)
        if settings.seed_demo_data:
            with SessionLocal() as db:
                seed_demo_data(db)
    except OperationalError as err:
        host = engine.url.render_as_string(hide_password=True)
        log.error("Cannot reach the database at %s: %s", host, str(err.orig).strip().splitlines()[0] if err.orig else err)
        raise SystemExit(f"Cannot reach the database at {host}. Check DATABASE_URL in .env and that the database accepts connections from this machine.") from err
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Everyday Market API", version="1.0.0", description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan,
        contact={"name": "storefront-backend", "url": "https://github.com/RaunakDasgupta/storefront-backend"},
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"] if settings.cors_origins.strip() == "*" else settings.cors_origin_list,
        allow_methods=["*"], allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    return app


app = create_app()
