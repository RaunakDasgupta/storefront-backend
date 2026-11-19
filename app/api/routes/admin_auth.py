from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.errors import COMMON_ERRORS, ErrorResponse
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AdminLoginIn, SessionOut, UserOut
from app.services import users

router = APIRouter(prefix="/admin/auth", tags=["Admin auth"])


@router.post(
    "/login", response_model=SessionOut, summary="Log in to the admin portal",
    description="Sign in with a work email or an employee ID. Demo account: `admin@storefront.test` (or `EMP-1001`) / `admin1234`. Admin accounts are provisioned, there is no sign-up.",
    responses={401: {"model": ErrorResponse, "description": "The email, employee ID or password is incorrect."}},
)
def admin_login(data: AdminLoginIn, db: Session = Depends(get_db)) -> SessionOut:
    user = users.authenticate_admin(db, data.identity, data.password)
    return SessionOut(user=UserOut(name=user.name, email=user.email), token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut, summary="Who am I?", responses={k: COMMON_ERRORS[k] for k in (401, 403)})
def admin_me(user: User = Depends(require_admin)) -> UserOut:
    return UserOut(name=user.name, email=user.email)
