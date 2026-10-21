import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataSourceKind, FuelType, Transmission, VehicleStatus

CURRENT_YEAR = datetime.now().year


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str = Field(description="Absoluta (https://...) o relativa al servidor (/media/...)")
    is_primary: bool
    position: int


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    kind: DataSourceKind
    url: str | None


class VehicleSummary(BaseModel):
    """Versión corta de un vehículo, usada dentro de reservas, órdenes y ventas."""

    id: uuid.UUID
    stock_number: str
    brand: str
    model: str
    year: int
    version: str
    price_mxn: float
    status: VehicleStatus
    primary_image: str | None

    @classmethod
    def from_model(cls, v) -> "VehicleSummary":
        return cls(
            id=v.id, stock_number=v.stock_number, brand=v.model.brand.name, model=v.model.name,
            year=v.year, version=v.version, price_mxn=float(v.price_mxn), status=v.status,
            primary_image=_primary_image(v),
        )


class VehicleOut(BaseModel):
    id: uuid.UUID
    stock_number: str
    brand: str
    model: str
    body_type: str | None
    year: int
    version: str
    price_mxn: float
    mileage_km: int
    color: str
    transmission: Transmission
    fuel_type: FuelType
    engine: str
    description: str | None
    status: VehicleStatus
    primary_image: str | None
    images: list[ImageOut]
    data_source: DataSourceOut | None
    row_version: int = Field(description="Enviar en PATCH para detectar ediciones simultáneas")
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, v) -> "VehicleOut":
        return cls(
            id=v.id, stock_number=v.stock_number, brand=v.model.brand.name, model=v.model.name,
            body_type=v.model.body_type, year=v.year, version=v.version, price_mxn=float(v.price_mxn),
            mileage_km=v.mileage_km, color=v.color, transmission=v.transmission, fuel_type=v.fuel_type,
            engine=v.engine, description=v.description, status=v.status, primary_image=_primary_image(v),
            images=[ImageOut.model_validate(i) for i in v.images],
            data_source=DataSourceOut.model_validate(v.data_source) if v.data_source else None,
            row_version=v.row_version, created_at=v.created_at, updated_at=v.updated_at,
        )


def _primary_image(v) -> str | None:
    primary = next((i for i in v.images if i.is_primary), None) or (v.images[0] if v.images else None)
    return primary.url if primary else None


class VehicleSort(str, Enum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    YEAR_DESC = "year_desc"
    YEAR_ASC = "year_asc"
    MILEAGE_ASC = "mileage_asc"


class VehicleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    stock_number: str | None = Field(default=None, pattern=r"^[A-Z0-9\-]{3,20}$",
                                     description="Opcional; si se omite se genera AM-XXXXXXXX")
    brand: str = Field(min_length=2, max_length=60)
    model: str = Field(min_length=1, max_length=80)
    body_type: str | None = Field(default=None, max_length=40)
    year: int = Field(ge=1990, le=CURRENT_YEAR + 1)
    version: str = Field(min_length=1, max_length=80)
    price_mxn: Decimal = Field(gt=0, le=50_000_000, max_digits=12, decimal_places=2)
    mileage_km: int = Field(default=0, ge=0, le=2_000_000)
    color: str = Field(min_length=2, max_length=40)
    transmission: Transmission
    fuel_type: FuelType
    engine: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=5000)


class VehicleUpdate(BaseModel):
    """Todos los campos son opcionales salvo row_version. El estado no se edita aquí:
    cambia solo mediante reservas, órdenes y ventas."""

    model_config = ConfigDict(str_strip_whitespace=True)

    row_version: int = Field(ge=1, description="row_version que tenía el vehículo al abrirlo")
    version: str | None = Field(default=None, min_length=1, max_length=80)
    year: int | None = Field(default=None, ge=1990, le=CURRENT_YEAR + 1)
    price_mxn: Decimal | None = Field(default=None, gt=0, le=50_000_000, max_digits=12, decimal_places=2)
    mileage_km: int | None = Field(default=None, ge=0, le=2_000_000)
    color: str | None = Field(default=None, min_length=2, max_length=40)
    transmission: Transmission | None = None
    fuel_type: FuelType | None = None
    engine: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=5000)


class ModelOut(BaseModel):
    id: int
    name: str
    body_type: str | None
    available: int = Field(description="Vehículos disponibles de este modelo")


class BrandOut(BaseModel):
    id: int
    name: str
    models: list[ModelOut]
