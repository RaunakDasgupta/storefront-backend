"""Checking a table of rows against the catalog and describing what an import would do."""
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.product import ImportSummary, ImportValidation
from app.services import products as product_service
from app.services.catalog_sheet import SheetResult, parse_sheet
from app.services.readers import FileProblem, read_upload


def describe(db: Session, result: SheetResult) -> ImportValidation:
    new, updates = product_service.classify(db, result.rows)
    return ImportValidation(
        rows=result.rows, issues=result.issues, fatal=result.fatal,
        summary=ImportSummary(total_rows=result.total_rows, valid=len(result.rows), new=new, updates=updates, skipped=result.skipped),
    )


def validate_table(db: Session, table: list[list[str]]) -> ImportValidation:
    return describe(db, parse_sheet(table, get_settings().max_import_rows))


def validate_file(db: Session, filename: str, content: bytes) -> ImportValidation:
    """A file the person uploaded. A file we cannot read comes back with `fatal` set, not as an HTTP error."""
    settings = get_settings()
    try:
        table = read_upload(filename, content, settings.max_import_rows)
    except FileProblem as problem:
        return describe(db, SheetResult(fatal=str(problem)))
    return validate_table(db, table)
