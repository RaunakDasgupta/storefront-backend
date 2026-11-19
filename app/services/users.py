"""Accounts: sign up, sign in, and the lookups the routes need."""
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password, verify_password
from app.models.employee import Employee
from app.models.user import User
from app.schemas.auth import RegisterIn


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def list_customers(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def list_employees(db: Session) -> list[Employee]:
    return list(db.scalars(select(Employee).order_by(Employee.id)))


def register_customer(db: Session, data: RegisterIn) -> User:
    if find_by_email(db, data.email) is not None:
        raise ApiError(409, "An account with this email already exists.")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two sign-ups with the same email at the same moment
        db.rollback()
        raise ApiError(409, "An account with this email already exists.")
    return user


def authenticate_customer(db: Session, email: str, password: str) -> User:
    user = find_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise ApiError(401, "The email or password is incorrect.")
    return user


def authenticate_employee(db: Session, identity: str, password: str) -> Employee:
    who = identity.strip().lower()
    employee = db.scalar(select(Employee).where(or_(func.lower(Employee.email) == who, func.lower(Employee.employee_id) == who)))
    if employee is None or not employee.is_active or not verify_password(password, employee.password_hash):
        raise ApiError(401, "The email, employee ID or password is incorrect.")
    return employee
