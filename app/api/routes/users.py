from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# from app.api.deps import require_admin
from app.core.errors import COMMON_ERRORS
from app.db.session import get_db
from app.schemas.auth import EmployeeRow, UserRow
from app.services import users

router = APIRouter(tags=["Users"])
ERRORS: dict = {}  # was {401, 403} while auth was on


@router.get("/users", response_model=list[UserRow], summary="List customers", responses=ERRORS,
            description="Every customer account, oldest first.")
def list_customers(
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return users.list_customers(db)


@router.get("/admin/users", response_model=list[EmployeeRow], summary="List admin users (employees)", responses=ERRORS,
            description="Every employee account, oldest first, with its employee ID. Employees are kept apart from customers, with their own ids.")
def list_admins(
    db: Session = Depends(get_db),
    # _: User = Depends(require_admin),  # auth disabled
):
    return users.list_employees(db)
