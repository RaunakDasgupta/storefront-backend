from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# from app.api.deps import require_admin
from app.core.errors import COMMON_ERRORS, ApiError, ErrorResponse
from app.db.session import get_db
# from app.models.user import User
from app.schemas.connect import ConnectIn
from app.schemas.product import ImportValidation
from app.services.importing.connectors import read_source
from app.services.importing.service import validate_table

router = APIRouter(prefix="/import", tags=["Import sources"])


@router.post(
    "/connect", response_model=ImportValidation, response_model_exclude_none=True, summary="Read the catalog from a database",
    description=(
        "Connects to a database, reads one table (read-only, up to the import row limit) and checks it exactly like a spreadsheet: the column "
        "names are the same (`SKU`, `Current Sales Price`, `Brand`, `quantity`...). Nothing is saved: send the returned `rows` to `POST /products/import`.\n\n"
        "**Enabled:** PostgreSQL, AWS RDS for PostgreSQL, SQLite (a file inside the server's `IMPORT_SQLITE_DIR`). "
        "**Not enabled (501):** S3, Google Cloud Storage, Cloud SQL, BigQuery."
    ),
    responses={
        **{k: COMMON_ERRORS[k] for k in (422,)},
        400: {"model": ErrorResponse, "description": "The database could not be reached or the table could not be read."},
        501: {"model": ErrorResponse, "description": "That source is not enabled on this server."},
    },
)
def connect(
    data: ConnectIn,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    result = validate_table(db, read_source(data.connector, data.service, data.settings))
    if result.fatal:
        raise ApiError(422, result.fatal)
    return result
