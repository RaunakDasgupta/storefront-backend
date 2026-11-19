from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

# from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.errors import COMMON_ERRORS, ApiError, ErrorResponse
from app.db.session import get_db
# from app.models.user import User
from app.schemas.product import (
    ImportRequest, ImportResult, ImportValidation, ProductCreate, ProductOut, ProductUpdate, ImportSummary,
)
from app.services import products as service
from app.services.importing.service import describe, validate_file
from app.services.catalog_sheet import SheetResult

router = APIRouter(prefix="/products", tags=["Products"])
ADMIN_ERRORS = {k: COMMON_ERRORS[k] for k in (422,)}  # was (401, 403, 422) while auth was on
NOT_FOUND = {404: {"model": ErrorResponse, "description": "No product with this id."}}


def _read_upload(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_bytes
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise ApiError(413, f"That file is larger than {limit // 1_000_000} MB. Split it and upload each part.")
    return content


@router.get("", response_model=list[ProductOut], response_model_exclude_none=True, summary="List the products",
            description="Every product that has not been deleted, in catalog order. Public: the storefront shows it to everyone.")
def list_products(db: Session = Depends(get_db)):
    return service.list_products(db)


@router.post(
    "", response_model=ProductOut, response_model_exclude_none=True, status_code=201, summary="Add a product",
    description="Admin 'Add product'. The id is made from the SKU. A SKU that already exists (in any capitals) is refused with 409.",
    responses={**ADMIN_ERRORS, 409: {"model": ErrorResponse, "description": "A product with this SKU already exists."}},
)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return service.create_product(db, data)


# ---- importing: these static paths come before /{product_id} ---------------------------------------------------------
@router.post(
    "/import", response_model=ImportResult, summary="Import SKUs (rows)",
    description=(
        "Adds new SKUs and updates existing ones, matched by SKU (any capitals). **Nothing is deleted.** A blank description, size or logo "
        "never wipes what is already there. If a row has `locations`, they replace the SKU's stock locations and `stock` becomes the "
        "available total. Send rows that came back from `/products/import/validate` or `/import/connect`."
    ),
    responses=ADMIN_ERRORS,
)
def import_products(
    data: ImportRequest,
    db: Session = Depends(get_db),
    # user: User = Depends(require_admin),  # auth disabled
) -> ImportResult:
    added, updated = service.import_rows(db, data.rows, employee_id=None, source="rows")
    return ImportResult(added=added, updated=updated)


@router.post(
    "/import/validate", response_model=ImportValidation, response_model_exclude_none=True, summary="Check a CSV or Excel file (nothing is saved)",
    description=(
        "Upload the catalog sheet as `.csv` (comma, semicolon or tab separated) or `.xlsx`. Returns the rows that passed, the problem rows with their "
        "spreadsheet line number, and how many SKUs would be new or updates. A file that cannot be used at all (empty, wrong type, missing "
        "the `SKU` or `Current Sales Price` column) comes back with `fatal` set. See the README for the column list."
    ),
    responses=ADMIN_ERRORS | {413: {"model": ErrorResponse, "description": "The file is too large."}},
)
def validate_import_file(
    file: UploadFile = File(description="A .csv or .xlsx file."),
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return validate_file(db, file.filename or "", _read_upload(file))


@router.post(
    "/import/file", response_model=ImportResult, summary="Import a CSV or Excel file",
    description="Validates the file like `/products/import/validate` and, when it is usable, imports the rows that passed. Rows with problems are skipped and recorded.",
    responses=ADMIN_ERRORS | {413: {"model": ErrorResponse, "description": "The file is too large."}},
)
def import_products_file(
    file: UploadFile = File(description="A .csv or .xlsx file."),
    db: Session = Depends(get_db),
    # user: User = Depends(require_admin),  # auth disabled
) -> ImportResult:
    checked = validate_file(db, file.filename or "", _read_upload(file))
    if checked.fatal:
        raise ApiError(422, checked.fatal)
    name = (file.filename or "").lower()
    added, updated = service.import_rows(
        db, checked.rows, employee_id=None, source="xlsx" if name.endswith((".xlsx", ".xlsm")) else "csv", filename=file.filename,
        issues=checked.issues, total_rows=checked.summary.total_rows,
    )
    return ImportResult(added=added, updated=updated)


# ---- one product ------------------------------------------------------------------------------------------------------
@router.get("/{product_id}", response_model=ProductOut, response_model_exclude_none=True, summary="Get one product", responses=NOT_FOUND)
def get_product(product_id: str, db: Session = Depends(get_db)):
    return service.get_product(db, product_id)


@router.patch(
    "/{product_id}", response_model=ProductOut, response_model_exclude_none=True, summary="Edit a product",
    description="Admin 'Edit product'. Only the fields you send change; send `null` for `size`, `was` or `image` to clear them. The SKU cannot be changed.",
    responses=ADMIN_ERRORS | NOT_FOUND,
)
def update_product(
    product_id: str,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return service.update_product(db, product_id, data.model_dump(exclude_unset=True))


@router.delete(
    "/{product_id}", status_code=204, summary="Delete a product",
    description="A soft delete: the product disappears from the storefront but is kept, so `/restore` (the Undo button) works and old orders keep their items.",
    responses=ADMIN_ERRORS | NOT_FOUND,
)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
) -> Response:
    service.delete_product(db, product_id)
    return Response(status_code=204)


@router.post("/{product_id}/restore", response_model=ProductOut, response_model_exclude_none=True, summary="Undo a delete", responses=ADMIN_ERRORS | NOT_FOUND)
def restore_product(
    product_id: str,
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return service.restore_product(db, product_id)
