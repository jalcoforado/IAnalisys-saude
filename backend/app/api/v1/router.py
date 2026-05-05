from fastapi import APIRouter
from app.api.v1.routes import health
from app.api.v1.routes import auth
from app.api.v1.routes import sync
from app.api.v1.routes import contaazul
from app.api.v1.routes import transform
from app.api.v1.routes import analytics
from app.api.v1.routes import dashboard
from app.api.v1.routes import financeiro
from app.api.v1.routes import home
from app.api.v1.routes import tenant
from app.api.v1.routes import permissions as permissions_route
from app.api.v1.routes import users as users_route

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(sync.router)
api_router.include_router(contaazul.router)
api_router.include_router(transform.router)
api_router.include_router(analytics.router)
api_router.include_router(dashboard.router)
api_router.include_router(financeiro.router)
api_router.include_router(home.router)
api_router.include_router(tenant.router)
api_router.include_router(permissions_route.router)
api_router.include_router(users_route.router)
