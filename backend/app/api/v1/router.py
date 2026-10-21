from fastapi import APIRouter

from app.api.v1 import auth, commerce, health, stats, vehicles, ws

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(vehicles.router)
api_router.include_router(commerce.reservations)
api_router.include_router(commerce.orders)
api_router.include_router(commerce.admin_router)
api_router.include_router(stats.router)
api_router.include_router(ws.router)
