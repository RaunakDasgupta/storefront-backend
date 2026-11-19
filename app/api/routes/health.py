from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["Health"])


class Health(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=Health, summary="Is the API (and its database) up?", responses={503: {"model": Health, "description": "The database cannot be reached."}})
def health(response: Response, db: Session = Depends(get_db)) -> Health:
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001  any failure means "down"
        response.status_code = 503
        return Health(status="degraded", database="down")
    return Health(status="ok", database="up")
