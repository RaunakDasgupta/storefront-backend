"""Turning an uploaded file into rows of text: CSV (comma, semicolon or tab separated) and Excel (.xlsx)."""
import csv
import io
from datetime import date, datetime

from app.core.errors import ApiError


class FileProblem(Exception):
    """The whole file is unusable. The message is for the person who uploaded it."""


def read_upload(filename: str, content: bytes, max_rows: int = 1000) -> list[list[str]]:
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return _read_xlsx(content, max_rows)
    if name.endswith(".xls"):
        raise FileProblem("Old .xls files are not supported. Save the file as .xlsx or .csv and upload it again.")
    if name.endswith(".csv") or name.endswith(".txt") or name.endswith(".tsv"):
        return _read_csv(content)
    raise FileProblem("Choose a .csv or .xlsx file.")


def _read_csv(content: bytes) -> list[list[str]]:
    if not content.strip():
        raise FileProblem("The file is empty.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")  # what Excel on Windows saves "CSV" as
    first_line = text.split("\n", 1)[0]
    delimiter = max((",", ";", "\t"), key=first_line.count)
    return [list(row) for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)]


def _read_xlsx(content: bytes, max_rows: int) -> list[list[str]]:
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (InvalidFileException, OSError, KeyError, ValueError) as err:
        raise FileProblem("That does not look like a valid .xlsx file.") from err
    except Exception as err:  # a corrupt zip surfaces as several different errors
        raise FileProblem("That does not look like a valid .xlsx file.") from err

    sheet = workbook.worksheets[0] if workbook.worksheets else None
    if sheet is None:
        raise FileProblem("The workbook has no sheets.")
    rows: list[list[str]] = []
    for values in sheet.iter_rows(values_only=True):
        rows.append([_cell(v) for v in values])
        if len(rows) > max_rows + 300:  # stop early on a huge sheet: the caller reports "too many rows"
            break
    workbook.close()
    # Excel pads every row to the sheet's width: cut trailing empty columns off the header
    return rows


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def to_api_error(problem: FileProblem) -> ApiError:
    return ApiError(422, str(problem))
