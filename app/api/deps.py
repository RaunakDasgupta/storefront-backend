"""Shared route dependencies: the database session and who is signed in."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import ADMIN, CUSTOMER, User

# shows the "Authorize" button in Swagger: paste the `token` from a login response
bearer = HTTPBearer(auto_error=False, description="Paste the `token` from POST /auth/login or POST /admin/auth/login.")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise ApiError(401, "Please log in.")
    claims = decode_access_token(credentials.credentials)
    if not claims:
        raise ApiError(401, "Your session has ended. Please log in again.")
    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise ApiError(401, "Your session has ended. Please log in again.")
    return user


def require_customer(user: User = Depends(current_user)) -> User:
    if user.role != CUSTOMER:
        raise ApiError(403, "This is for customers. Log in with a customer account.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != ADMIN:
        raise ApiError(403, "Only admins can do this.")
    return user
