from fastapi import APIRouter
from app.api.v1.routes import health
from app.api.v1.routes import auth
from app.api.v1.routes import sync
from app.api.v1.routes import contaazul
from app.api.v1.routes import transform

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(sync.router)
api_router.include_router(contaazul.router)
api_router.include_router(transform.router)
