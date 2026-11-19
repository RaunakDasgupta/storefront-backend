from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.errors import COMMON_ERRORS
from app.db.session import get_db
from app.models.user import ADMIN, CUSTOMER, User
from app.schemas.auth import UserRow
from app.services import users

router = APIRouter(tags=["Users"])
ERRORS = {k: COMMON_ERRORS[k] for k in (401, 403)}


@router.get("/users", response_model=list[UserRow], response_model_exclude_none=True, summary="List customers", responses=ERRORS,
            description="Admin only. Every customer account, oldest first.")
def list_customers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return users.list_by_role(db, CUSTOMER)


@router.get("/admin/users", response_model=list[UserRow], response_model_exclude_none=True, summary="List admin users", responses=ERRORS,
            description="Admin only. Every admin account, oldest first, with its employee ID.")
def list_admins(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return users.list_by_role(db, ADMIN)
