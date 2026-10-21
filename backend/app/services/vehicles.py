"""Catálogo: consulta con filtros, alta, edición, baja controlada y fotografías."""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core import events
from app.core.config import get_settings
from app.core.errors import Conflict, DomainError, NotFound
from app.models import Brand, User, Vehicle, VehicleImage, VehicleModel
from app.models.enums import FuelType, OperationSource, Transmission, VehicleStatus
from app.schemas.vehicle import VehicleCreate, VehicleOut, VehicleSort, VehicleUpdate
from app.services import history

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MEDIA_URL_PREFIX = "/media"

SORTS = {
    VehicleSort.NEWEST: (Vehicle.created_at.desc(), Vehicle.stock_number),
    VehicleSort.PRICE_ASC: (Vehicle.price_mxn.asc(), Vehicle.stock_number),
    VehicleSort.PRICE_DESC: (Vehicle.price_mxn.desc(), Vehicle.stock_number),
    VehicleSort.YEAR_DESC: (Vehicle.year.desc(), Vehicle.price_mxn.asc()),
    VehicleSort.YEAR_ASC: (Vehicle.year.asc(), Vehicle.price_mxn.asc()),
    VehicleSort.MILEAGE_ASC: (Vehicle.mileage_km.asc(), Vehicle.price_mxn.asc()),
}


@dataclass
class VehicleFilters:
    q: str | None = None
    brand: str | None = None
    model: str | None = None
    body_type: str | None = None
    status: VehicleStatus | None = None
    transmission: Transmission | None = None
    fuel_type: FuelType | None = None
    year_min: int | None = None
    year_max: int | None = None
    price_min: float | None = None
    price_max: float | None = None
    mileage_max: int | None = None
    sort: VehicleSort = VehicleSort.NEWEST
    page: int = 1
    page_size: int = 20


def _base_query() -> Select:
    return (
        select(Vehicle)
        .options(selectinload(Vehicle.images), joinedload(Vehicle.data_source))
        .where(Vehicle.deleted_at.is_(None))
    )


def _event_payload(v: Vehicle) -> dict:
    return VehicleOut.from_model(v).model_dump(mode="json")


def get_vehicle(db: Session, vehicle_id: uuid.UUID) -> Vehicle:
    vehicle = db.scalar(_base_query().where(Vehicle.id == vehicle_id))
    if not vehicle:
        raise NotFound("Vehículo no encontrado", "vehicle_not_found")
    return vehicle


def list_vehicles(db: Session, f: VehicleFilters) -> tuple[list[Vehicle], int]:
    stmt = select(Vehicle.id).join(Vehicle.model).join(VehicleModel.brand).where(Vehicle.deleted_at.is_(None))
    if f.q:
        like = f"%{f.q.strip()}%"
        stmt = stmt.where(or_(
            Brand.name.ilike(like), VehicleModel.name.ilike(like), Vehicle.version.ilike(like),
            Vehicle.color.ilike(like), Vehicle.stock_number.ilike(like), Vehicle.engine.ilike(like),
        ))
    if f.brand:
        stmt = stmt.where(Brand.name.ilike(f.brand.strip()))
    if f.model:
        stmt = stmt.where(VehicleModel.name.ilike(f.model.strip()))
    if f.body_type:
        stmt = stmt.where(VehicleModel.body_type.ilike(f.body_type.strip()))
    for column, value in ((Vehicle.status, f.status), (Vehicle.transmission, f.transmission),
                          (Vehicle.fuel_type, f.fuel_type)):
        if value is not None:
            stmt = stmt.where(column == value)
    if f.year_min is not None:
        stmt = stmt.where(Vehicle.year >= f.year_min)
    if f.year_max is not None:
        stmt = stmt.where(Vehicle.year <= f.year_max)
    if f.price_min is not None:
        stmt = stmt.where(Vehicle.price_mxn >= f.price_min)
    if f.price_max is not None:
        stmt = stmt.where(Vehicle.price_mxn <= f.price_max)
    if f.mileage_max is not None:
        stmt = stmt.where(Vehicle.mileage_km <= f.mileage_max)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    ids = db.scalars(stmt.order_by(*SORTS[f.sort]).limit(f.page_size).offset((f.page - 1) * f.page_size)).all()
    if not ids:
        return [], total
    by_id = {v.id: v for v in db.scalars(_base_query().where(Vehicle.id.in_(ids))).unique()}
    return [by_id[i] for i in ids], total


def list_brands(db: Session) -> list[dict]:
    available = (
        func.count(Vehicle.id)
        .filter(Vehicle.status == VehicleStatus.DISPONIBLE, Vehicle.deleted_at.is_(None))
    )
    rows = db.execute(
        select(Brand.id, Brand.name, VehicleModel.id, VehicleModel.name, VehicleModel.body_type, available)
        .join(VehicleModel, VehicleModel.brand_id == Brand.id)
        .outerjoin(Vehicle, Vehicle.model_id == VehicleModel.id)
        .group_by(Brand.id, Brand.name, VehicleModel.id, VehicleModel.name, VehicleModel.body_type)
        .order_by(Brand.name, VehicleModel.name)
    ).all()
    brands: dict[int, dict] = {}
    for brand_id, brand_name, model_id, model_name, body, count in rows:
        brands.setdefault(brand_id, {"id": brand_id, "name": brand_name, "models": []})["models"].append(
            {"id": model_id, "name": model_name, "body_type": body, "available": count}
        )
    return list(brands.values())


def _get_or_create_model(db: Session, brand_name: str, model_name: str, body_type: str | None) -> VehicleModel:
    brand = db.scalar(select(Brand).where(func.lower(Brand.name) == brand_name.lower()))
    if not brand:
        brand = Brand(name=brand_name)
        db.add(brand)
        db.flush()
    model = db.scalar(select(VehicleModel).where(
        VehicleModel.brand_id == brand.id, func.lower(VehicleModel.name) == model_name.lower()
    ))
    if not model:
        model = VehicleModel(brand_id=brand.id, name=model_name, body_type=body_type)
        db.add(model)
        db.flush()
    return model


def create_vehicle(db: Session, data: VehicleCreate, actor: User, source: OperationSource) -> Vehicle:
    stock = data.stock_number or f"AM-{uuid.uuid4().hex[:8].upper()}"
    if db.scalar(select(Vehicle.id).where(Vehicle.stock_number == stock)):
        raise Conflict(f"Ya existe un vehículo con el folio {stock}", "stock_number_taken")
    model = _get_or_create_model(db, data.brand, data.model, data.body_type)
    vehicle = Vehicle(
        stock_number=stock, model_id=model.id,
        **data.model_dump(exclude={"stock_number", "brand", "model", "body_type"}),
    )
    db.add(vehicle)
    db.flush()
    history.record(db, operation="vehiculo_registrado", source=source, actor_id=actor.id,
                   vehicle_id=vehicle.id, to_status=vehicle.status,
                   details={"stock_number": stock, "price_mxn": vehicle.price_mxn})
    db.commit()
    vehicle = get_vehicle(db, vehicle.id)
    events.publish("vehicle.created", _event_payload(vehicle))
    return vehicle


def update_vehicle(db: Session, vehicle_id: uuid.UUID, data: VehicleUpdate, actor: User,
                   source: OperationSource) -> Vehicle:
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle.row_version != data.row_version:
        raise Conflict("El vehículo fue modificado por otro usuario; recarga e intenta de nuevo.",
                       "version_conflict")
    if vehicle.status == VehicleStatus.VENDIDO:
        raise Conflict("Un vehículo vendido no se puede editar", "vehicle_sold")

    changes = {}
    for field, new in data.model_dump(exclude_unset=True, exclude={"row_version"}).items():
        old = getattr(vehicle, field)
        if new is not None and old != new:
            changes[field] = {"antes": old, "despues": new}
            setattr(vehicle, field, new)
    if not changes:
        return vehicle

    db.flush()  # aquí SQLAlchemy incrementa row_version (bloqueo optimista)
    operation = "precio_actualizado" if set(changes) == {"price_mxn"} else "vehiculo_actualizado"
    history.record(db, operation=operation, source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   details={"cambios": changes})
    db.commit()
    vehicle = get_vehicle(db, vehicle.id)
    events.publish("vehicle.updated", _event_payload(vehicle) | {"changed": sorted(changes)})
    return vehicle


def delete_vehicle(db: Session, vehicle_id: uuid.UUID, actor: User, source: OperationSource) -> None:
    """Baja controlada: solo vehículos disponibles; el registro se conserva con deleted_at."""
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle.status != VehicleStatus.DISPONIBLE:
        raise Conflict(f"No se puede eliminar un vehículo {vehicle.status.value}", "vehicle_not_deletable")
    vehicle.deleted_at = datetime.now(timezone.utc)
    history.record(db, operation="vehiculo_eliminado", source=source, actor_id=actor.id,
                   vehicle_id=vehicle.id, from_status=vehicle.status,
                   details={"stock_number": vehicle.stock_number})
    db.commit()
    events.publish("vehicle.deleted", {"id": str(vehicle.id), "stock_number": vehicle.stock_number})


# ---------- Fotografías ----------
def add_image(db: Session, vehicle_id: uuid.UUID, content: bytes, content_type: str,
              actor: User, source: OperationSource) -> Vehicle:
    settings = get_settings()
    vehicle = get_vehicle(db, vehicle_id)
    ext = ALLOWED_IMAGE_TYPES.get(content_type)
    if not ext:
        raise DomainError("Formato no permitido; usa JPG, PNG o WEBP", "invalid_image_type")
    if len(content) > settings.max_image_mb * 1024 * 1024:
        raise DomainError(f"La imagen supera {settings.max_image_mb} MB", "image_too_large")
    if not _looks_like_image(content, ext):
        raise DomainError("El archivo no es una imagen válida", "invalid_image")

    relative = Path("vehicles") / str(vehicle.id) / f"{uuid.uuid4().hex}{ext}"
    target = settings.media_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    is_first = not vehicle.images
    db.add(VehicleImage(vehicle_id=vehicle.id, url=f"{MEDIA_URL_PREFIX}/{relative.as_posix()}",
                        is_primary=is_first, position=len(vehicle.images)))
    history.record(db, operation="foto_agregada", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   details={"archivo": relative.name})
    db.commit()
    db.expire(vehicle)
    vehicle = get_vehicle(db, vehicle.id)
    events.publish("vehicle.updated", _event_payload(vehicle) | {"changed": ["images"]})
    return vehicle


def set_primary_image(db: Session, vehicle_id: uuid.UUID, image_id: int, actor: User,
                      source: OperationSource) -> Vehicle:
    vehicle = get_vehicle(db, vehicle_id)
    image = next((i for i in vehicle.images if i.id == image_id), None)
    if not image:
        raise NotFound("Imagen no encontrada", "image_not_found")
    for i in vehicle.images:
        i.is_primary = False
    db.flush()  # primero se apagan todas (índice único de foto principal)
    image.is_primary = True
    history.record(db, operation="foto_principal", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   details={"image_id": image_id})
    db.commit()
    vehicle = get_vehicle(db, vehicle.id)
    events.publish("vehicle.updated", _event_payload(vehicle) | {"changed": ["images"]})
    return vehicle


def delete_image(db: Session, vehicle_id: uuid.UUID, image_id: int, actor: User,
                 source: OperationSource) -> Vehicle:
    vehicle = get_vehicle(db, vehicle_id)
    image = next((i for i in vehicle.images if i.id == image_id), None)
    if not image:
        raise NotFound("Imagen no encontrada", "image_not_found")
    was_primary = image.is_primary
    vehicle.images.remove(image)  # delete-orphan la borra de la BD
    db.flush()
    if was_primary and vehicle.images:
        vehicle.images[0].is_primary = True
    if image.url.startswith(MEDIA_URL_PREFIX + "/"):
        (get_settings().media_dir / image.url.removeprefix(MEDIA_URL_PREFIX + "/")).unlink(missing_ok=True)
    history.record(db, operation="foto_eliminada", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   details={"image_id": image_id})
    db.commit()
    vehicle = get_vehicle(db, vehicle.id)
    events.publish("vehicle.updated", _event_payload(vehicle) | {"changed": ["images"]})
    return vehicle


def _looks_like_image(content: bytes, ext: str) -> bool:
    """Valida la firma binaria del archivo, no solo el Content-Type que manda el cliente."""
    signatures = {".jpg": [b"\xff\xd8\xff"], ".png": [b"\x89PNG\r\n\x1a\n"], ".webp": [b"RIFF"]}
    return any(content.startswith(sig) for sig in signatures[ext]) and (ext != ".webp" or content[8:12] == b"WEBP")
