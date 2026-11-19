"""Shared route dependencies: the database session and who is signed in."""
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import ADMIN, User

# shows the "Authorize" button in Swagger: paste the `token` from a login response
bearer = HTTPBearer(auto_error=False, description="Paste the `token` from POST /auth/login or POST /admin/auth/login.")


def _find(db: Session, claims: dict) -> User | Employee | None:
    """The account a token points at: the token's role says which table its id is from."""
    table = Employee if claims.get("role") == ADMIN else User
    return db.get(table, int(claims["sub"]))


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User | Employee:
    if credentials is None:
        raise ApiError(401, "Please log in.")
    claims = decode_access_token(credentials.credentials)
    account = _find(db, claims) if claims else None
    if account is None or not account.is_active:
        raise ApiError(401, "Your session has ended. Please log in again.")
    return account


def require_customer(user: User | Employee = Depends(current_user)) -> User:
    if not isinstance(user, User):
        raise ApiError(403, "This is for customers. Log in with a customer account.")
    return user


def require_admin(user: User | Employee = Depends(current_user)) -> Employee:
    if not isinstance(user, Employee):
        raise ApiError(403, "Only admins can do this.")
    return user


def acting_as(fallback_role: str, *, any_role: bool = False):
    """Stand-in while the auth requirement is switched off (see `# auth disabled` in the routes).

    Uses the account of a valid token when one is sent (only if it is of `fallback_role`, unless `any_role`), otherwise the
    first active customer (or employee), so orders and payments still belong to a real account.
    """
    table = Employee if fallback_role == ADMIN else User

    def dependency(authorization: str | None = Header(None, include_in_schema=False), db: Session = Depends(get_db)) -> User | Employee:
        # read the header by hand (not through `bearer`) so Swagger shows no lock and no Authorize button
        token = authorization.removeprefix("Bearer ").strip() if authorization else ""
        claims = decode_access_token(token) if token else None
        account = _find(db, claims) if claims else None
        if account is not None and account.is_active and (any_role or isinstance(account, table)):
            return account
        account = db.scalar(select(table).where(table.is_active).order_by(table.id))
        if account is None:
            raise ApiError(404, f"There is no {fallback_role} account yet.")
        return account

    return dependency
