from fastapi import APIRouter

from app.api.v1 import auth, categories, grants, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(grants.router)
api_router.include_router(categories.router)
