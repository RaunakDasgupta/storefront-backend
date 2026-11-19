"""Shared route dependencies: the database session and who is signed in."""
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
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


def acting_as(fallback_role: str, *, any_role: bool = False):
    """Stand-in while the auth requirement is switched off (see `# auth disabled` in the routes).

    Uses the user of a valid token when one is sent (only if their role is `fallback_role`, unless `any_role`), otherwise the
    first active account with `fallback_role`, so orders and payments still belong to a real user.
    """
    def dependency(authorization: str | None = Header(None, include_in_schema=False), db: Session = Depends(get_db)) -> User:
        # read the header by hand (not through `bearer`) so Swagger shows no lock and no Authorize button
        token = authorization.removeprefix("Bearer ").strip() if authorization else ""
        claims = decode_access_token(token) if token else None
        user = db.get(User, int(claims["sub"])) if claims else None
        if user is not None and user.is_active and (any_role or user.role == fallback_role):
            return user
        user = db.scalar(select(User).where(User.role == fallback_role, User.is_active).order_by(User.id))
        if user is None:
            raise ApiError(404, f"There is no {fallback_role} account yet.")
        return user

    return dependency
