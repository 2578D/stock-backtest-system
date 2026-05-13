"""V1 API router — aggregates all module routes."""

from fastapi import APIRouter

from app.api.v1.auth.endpoints import router as auth_router
from app.api.v1.dashboard.endpoints import router as dashboard_router
from app.api.v1.data.endpoints import router as data_router
from app.api.v1.strategies.endpoints import router as strategies_router
from app.api.v1.backtests.endpoints import router as backtests_router
from app.api.v1.system.endpoints import router as system_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["仪表盘"])
api_router.include_router(data_router, prefix="/data", tags=["数据"])
api_router.include_router(strategies_router, prefix="/strategies", tags=["策略"])
api_router.include_router(backtests_router, prefix="/backtests", tags=["回测"])
api_router.include_router(system_router, prefix="/system", tags=["系统"])
