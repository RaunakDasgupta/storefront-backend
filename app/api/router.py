from fastapi import APIRouter

from app.api.routes import admin_auth, auth, health, imports, orders, payments, products, users

api_router = APIRouter()
for module in (health, auth, admin_auth, products, orders, payments, imports, users):
    api_router.include_router(module.router)
