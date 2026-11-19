from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# from app.api.deps import require_admin
from app.api.deps import acting_as
from app.core.errors import COMMON_ERRORS, ErrorResponse
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import ADMIN, User
from app.schemas.auth import AdminLoginIn, SessionOut, UserOut
from app.services import users

router = APIRouter(prefix="/admin/auth", tags=["Admin auth"])


@router.post(
    "/login", response_model=SessionOut, summary="Log in to the admin portal",
    description=(
        "Sign in with a work email or an employee ID. Admin accounts are provisioned, there is no sign-up.\n\n"
        "**Demo admin:** `admin@storefront.test` or `EMP-1001`, password `admin1234`."
    ),
    responses={401: {"model": ErrorResponse, "description": "The email, employee ID or password is incorrect."}},
)
def admin_login(data: AdminLoginIn, db: Session = Depends(get_db)) -> SessionOut:
    user = users.authenticate_admin(db, data.identity, data.password)
    return SessionOut(user=UserOut(name=user.name, email=user.email), token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut, summary="Who am I?", description="The account in the token, or the first admin account when no token is sent.")
def admin_me(
    user: User = Depends(acting_as(ADMIN)),  # auth disabled, was Depends(require_admin)
) -> UserOut:
    return UserOut(name=user.name, email=user.email)
