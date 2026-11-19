"""Accounts: sign up, sign in, and the lookups the routes need."""
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password, verify_password
from app.models.user import ADMIN, CUSTOMER, User
from app.schemas.auth import RegisterIn


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def list_by_role(db: Session, role: str) -> list[User]:
    return list(db.scalars(select(User).where(User.role == role).order_by(User.id)))


def register_customer(db: Session, data: RegisterIn) -> User:
    if find_by_email(db, data.email) is not None:
        raise ApiError(409, "An account with this email already exists.")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password), role=CUSTOMER)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise ApiError(409, "An account with this email already exists.")
    return user


def authenticate_customer(db: Session, email: str, password: str) -> User:
    user = find_by_email(db, email)
    if user is None or user.role != CUSTOMER or not user.is_active or not verify_password(password, user.password_hash):
        raise ApiError(401, "The email or password is incorrect.")
    return user


def authenticate_admin(db: Session, identity: str, password: str) -> User:
    who = identity.strip().lower()
    user = db.scalar(select(User).where(User.role == ADMIN, or_(func.lower(User.email) == who, func.lower(User.employee_id) == who)))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise ApiError(401, "The email, employee ID or password is incorrect.")
    return user
