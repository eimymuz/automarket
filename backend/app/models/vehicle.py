import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger,
    String, Text, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.catalog import DataSource, VehicleModel
from app.models.enums import FuelType, Transmission, VehicleStatus, pg_enum


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("year BETWEEN 1990 AND 2100", name="year_range"),
        CheckConstraint("price_mxn > 0", name="price_positive"),
        CheckConstraint("mileage_km >= 0", name="mileage_non_negative"),
        Index("ix_vehicles_status_active", "status", postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stock_number: Mapped[str] = mapped_column(String(20), unique=True)  # folio visible: AM-00001
    model_id: Mapped[int] = mapped_column(ForeignKey("vehicle_models.id"), index=True)
    year: Mapped[int] = mapped_column(SmallInteger, index=True)
    version: Mapped[str] = mapped_column(String(80))  # versión / trim: "Touring", "EX"...
    price_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 2), index=True)
    mileage_km: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(40))
    transmission: Mapped[Transmission] = mapped_column(pg_enum(Transmission, "transmission"))
    fuel_type: Mapped[FuelType] = mapped_column(pg_enum(FuelType, "fuel_type"))
    engine: Mapped[str] = mapped_column(String(80))  # "1.5L Turbo 4 cil."
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[VehicleStatus] = mapped_column(
        pg_enum(VehicleStatus, "vehicle_status"),
        default=VehicleStatus.DISPONIBLE,
        server_default=VehicleStatus.DISPONIBLE.value,
    )
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"))
    # Eliminación controlada: el registro se marca, no se borra (conserva historial y ventas)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bloqueo optimista: evita que dos clientes sobrescriban cambios del otro sin saberlo
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    model: Mapped[VehicleModel] = relationship(lazy="joined")
    data_source: Mapped[DataSource | None] = relationship()
    images: Mapped[list["VehicleImage"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan", order_by="VehicleImage.position"
    )

    __mapper_args__ = {"version_id_col": row_version}


class VehicleImage(Base):
    __tablename__ = "vehicle_images"
    __table_args__ = (
        # Solo una foto principal por vehículo
        Index(
            "uq_vehicle_images_one_primary", "vehicle_id",
            unique=True, postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    position: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vehicle: Mapped[Vehicle] = relationship(back_populates="images")
