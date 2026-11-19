"""One error shape for the whole API: `{ "message": "..." }`, which is what the frontend shows to people."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("storefront")


class ErrorResponse(BaseModel):
    """What every 4xx and 5xx response looks like."""

    message: str

    model_config = {"json_schema_extra": {"examples": [{"message": "The email or password is incorrect."}]}}


class ApiError(HTTPException):
    """Raise this from services. `message` goes straight to the person using the app."""

    def __init__(self, status_code: int, message: str):
        super().__init__(status_code=status_code, detail=message)


# the responses every route can give, so Swagger shows them
COMMON_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token."},
    403: {"model": ErrorResponse, "description": "Signed in, but not allowed to do this."},
    422: {"model": ErrorResponse, "description": "The request body or parameters are not valid."},
}


def _field_name(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        return JSONResponse({"message": message}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = []
        for err in exc.errors():
            field = _field_name(err["loc"])
            problems.append(f"{field}: {err['msg']}" if field else err["msg"])
        shown = "; ".join(problems[:5]) + ("; ..." if len(problems) > 5 else "")
        return JSONResponse({"message": f"Check the request: {shown}"}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse({"message": "Something went wrong on the server. Try again."}, status_code=500)
