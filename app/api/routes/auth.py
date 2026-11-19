from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_customer
from app.core.errors import COMMON_ERRORS, ErrorResponse
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, SessionOut, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["Customer auth"])


def _session(user: User) -> SessionOut:
    return SessionOut(user=UserOut(name=user.name, email=user.email), token=create_access_token(user.id, user.role))


@router.post(
    "/register", response_model=SessionOut, status_code=201, summary="Create a customer account",
    description="Creates the account and signs the customer in, so the storefront can carry on straight to checkout.",
    responses={409: {"model": ErrorResponse, "description": "An account with this email already exists."}, 422: COMMON_ERRORS[422]},
)
def register(data: RegisterIn, db: Session = Depends(get_db)) -> SessionOut:
    return _session(users.register_customer(db, data))


@router.post(
    "/login", response_model=SessionOut, summary="Log in as a customer",
    description=(
        "Admin accounts cannot log in here, use `/admin/auth/login`.\n\n"
        "**Demo customers** (password `customer123`): `customer@storefront.test` (Alex Morgan), `liam.chen@example.com`, "
        "`sofia.rossi@example.com`, `noah.williams@example.com`."
    ),
    responses={401: {"model": ErrorResponse, "description": "The email or password is incorrect."}},
)
def login(data: LoginIn, db: Session = Depends(get_db)) -> SessionOut:
    return _session(users.authenticate_customer(db, data.email, data.password))


@router.get("/me", response_model=UserOut, summary="Who am I?", responses={k: COMMON_ERRORS[k] for k in (401, 403)})
def me(user: User = Depends(require_customer)) -> UserOut:
    return UserOut(name=user.name, email=user.email)
