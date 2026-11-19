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
from app.db.migrate import upgrade_to_head
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine

log = logging.getLogger("storefront")

DESCRIPTION = """
The API behind **Everyday Market**: the customer storefront and the admin portal.

### Try it in this page
1. Open **Customer auth → POST /auth/login** (demo: `customer@storefront.test` / `customer123`) or
   **Admin auth → POST /admin/auth/login** (demo: `admin@storefront.test` or `EMP-1001` / `admin1234`) and press *Try it out*.
2. Copy the `token` from the response, press **Authorize** (top right) and paste it.
3. Every locked route now works as that person. Customers see their own orders; admins see everyone's and can manage products.

### Errors
Every error has the same shape: `{ "message": "..." }`. `401` means log in, `403` means you are not allowed, `409` means a conflict
(duplicate SKU, out of stock...), `422` means the request is not valid, `402` means a payment problem.

### The catalog sheet (CSV / Excel import)
One row per SKU, or one row per SKU and stock location. Header names are not case sensitive. Columns:

| Column | Notes |
|---|---|
| **SKU** (required) | Unique. The product name and size are taken from it when there is no `Name` column: `10014-Bru Gold 100g` becomes *Bru Gold*, *100g*. |
| **Current Sales Price** (required) | A number, for example `249`. |
| PID, Country, Business Group, Category, Brand, SubBrand, Segment, Form | Descriptive. Category defaults to `General`. |
| system_id, location_id, quantity, uom, status | Where the stock sits. `status` is AVAILABLE, BLOCKED, DAMAGED, HOLD or QUARANTINE and only AVAILABLE stock can be sold. `uom` defaults to EA. |
| Name, Size, Channel (`retail`/`bulk`), Compare At Price, Description, Logo URL | Optional extras. |

Unknown columns are ignored. Check a file with **POST /products/import/validate** before importing it.
"""

TAGS = [
    {"name": "Health", "description": "Is the server up, and can it reach its database?"},
    {"name": "Customer auth", "description": "Sign up and log in to the storefront."},
    {"name": "Admin auth", "description": "Log in to the admin portal."},
    {"name": "Products", "description": "The catalog: list, add, edit, delete and undo, plus importing CSV / Excel files."},
    {"name": "Orders", "description": "Checkout, My orders, and the admin's order management."},
    {"name": "Payments", "description": "The dummy card gateway used at checkout."},
    {"name": "Import sources", "description": "Reading the catalog from a database instead of a file."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    try:
        if settings.auto_migrate:
            upgrade_to_head()
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
