import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models import User
from app.services import stats as svc

router = APIRouter(prefix="/stats", tags=["Estadísticas"])


class VehicleTotals(BaseModel):
    total: int
    by_status: dict[str, int]
    inventory_value_mxn: float


class BrandStat(BaseModel):
    brand: str
    total: int
    available: int
    avg_price_mxn: float


class BodyTypeStat(BaseModel):
    body_type: str
    total: int


class RangeStat(BaseModel):
    range: str
    total: int


class MonthStat(BaseModel):
    month: str
    total: int
    revenue_mxn: float


class SalesStats(BaseModel):
    total: int
    revenue_mxn: float
    last_30_days: int
    revenue_last_30_days_mxn: float
    monthly: list[MonthStat]


class Activity(BaseModel):
    id: int
    operation: str
    source: str
    vehicle_id: uuid.UUID | None
    stock_number: str | None
    actor: str | None
    to_status: str | None
    created_at: datetime


class DashboardOut(BaseModel):
    vehicles: VehicleTotals
    by_brand: list[BrandStat]
    by_body_type: list[BodyTypeStat]
    price_ranges: list[RangeStat]
    reservations_active: int
    orders_by_status: dict[str, int]
    sales: SalesStats
    recent_activity: list[Activity]


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """**Admin.** Todo lo que necesita el dashboard de AutoMarket.exe en una sola llamada."""
    return svc.dashboard(db)
