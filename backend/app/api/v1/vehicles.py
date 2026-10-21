import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_source, require_admin
from app.db.session import get_db
from app.models import OperationHistory, User
from app.models.enums import FuelType, OperationSource, Transmission, VehicleStatus
from app.schemas.commerce import HistoryOut
from app.schemas.common import ErrorOut, Page
from app.schemas.vehicle import BrandOut, VehicleCreate, VehicleOut, VehicleSort, VehicleUpdate
from app.services import vehicles as svc

router = APIRouter(tags=["Vehículos"])
ERRORS = {404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


def vehicle_filters(
    q: str | None = Query(None, max_length=100, description="Texto libre: marca, modelo, versión, color, folio"),
    brand: str | None = Query(None, max_length=60),
    model: str | None = Query(None, max_length=80),
    body_type: str | None = Query(None, max_length=40, description="SUV, Sedán, Hatchback, Pickup..."),
    status: VehicleStatus | None = None,
    transmission: Transmission | None = None,
    fuel_type: FuelType | None = None,
    year_min: int | None = Query(None, ge=1990, le=2100),
    year_max: int | None = Query(None, ge=1990, le=2100),
    price_min: float | None = Query(None, ge=0),
    price_max: float | None = Query(None, ge=0),
    mileage_max: int | None = Query(None, ge=0),
    sort: VehicleSort = VehicleSort.NEWEST,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> svc.VehicleFilters:
    return svc.VehicleFilters(**locals())


@router.get("/brands", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db)):
    """Marcas y modelos con el número de unidades disponibles (para armar los filtros)."""
    return svc.list_brands(db)


@router.get("/vehicles", response_model=Page[VehicleOut])
def list_vehicles(filters: svc.VehicleFilters = Depends(vehicle_filters), db: Session = Depends(get_db)):
    """Catálogo público con búsqueda, filtros, orden y paginación. No requiere sesión."""
    items, total = svc.list_vehicles(db, filters)
    return Page(items=[VehicleOut.from_model(v) for v in items], total=total,
                page=filters.page, page_size=filters.page_size)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleOut, responses=ERRORS)
def get_vehicle(vehicle_id: uuid.UUID, db: Session = Depends(get_db)):
    return VehicleOut.from_model(svc.get_vehicle(db, vehicle_id))


@router.post("/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin),
                   source: OperationSource = Depends(get_source)):
    """**Admin.** Registra un vehículo; la marca y el modelo se crean si no existen."""
    return VehicleOut.from_model(svc.create_vehicle(db, data, admin, source))


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut, responses=ERRORS)
def update_vehicle(vehicle_id: uuid.UUID, data: VehicleUpdate, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin), source: OperationSource = Depends(get_source)):
    """**Admin.** Edita campos. Responde **409 version_conflict** si `row_version` no coincide
    (alguien más modificó el vehículo)."""
    return VehicleOut.from_model(svc.update_vehicle(db, vehicle_id, data, admin, source))


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_vehicle(vehicle_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin),
                   source: OperationSource = Depends(get_source)):
    """**Admin.** Baja controlada (solo vehículos *disponibles*); se conserva el registro y su historial."""
    svc.delete_vehicle(db, vehicle_id, admin, source)


@router.post("/vehicles/{vehicle_id}/images", response_model=VehicleOut, status_code=status.HTTP_201_CREATED,
             responses=ERRORS)
async def upload_image(vehicle_id: uuid.UUID, file: UploadFile = File(..., description="JPG, PNG o WEBP"),
                       db: Session = Depends(get_db), admin: User = Depends(require_admin),
                       source: OperationSource = Depends(get_source)):
    """**Admin.** Sube una fotografía. La primera foto de un vehículo queda como principal."""
    content = await file.read()
    return VehicleOut.from_model(svc.add_image(db, vehicle_id, content, file.content_type or "", admin, source))


@router.post("/vehicles/{vehicle_id}/images/{image_id}/primary", response_model=VehicleOut, responses=ERRORS)
def set_primary_image(vehicle_id: uuid.UUID, image_id: int, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin), source: OperationSource = Depends(get_source)):
    return VehicleOut.from_model(svc.set_primary_image(db, vehicle_id, image_id, admin, source))


@router.delete("/vehicles/{vehicle_id}/images/{image_id}", response_model=VehicleOut, responses=ERRORS)
def delete_image(vehicle_id: uuid.UUID, image_id: int, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin), source: OperationSource = Depends(get_source)):
    return VehicleOut.from_model(svc.delete_image(db, vehicle_id, image_id, admin, source))


@router.get("/vehicles/{vehicle_id}/history", response_model=list[HistoryOut], responses=ERRORS)
def vehicle_history(vehicle_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """**Admin.** Historial de operaciones de un vehículo, del más reciente al más antiguo."""
    svc.get_vehicle(db, vehicle_id)
    return db.scalars(select(OperationHistory).where(OperationHistory.vehicle_id == vehicle_id)
                      .order_by(OperationHistory.created_at.desc(), OperationHistory.id.desc())).all()
