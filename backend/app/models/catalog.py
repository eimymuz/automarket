"""Catálogos normalizados: marcas, modelos y procedencia de los datos."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DataSourceKind, pg_enum


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)

    models: Mapped[list["VehicleModel"]] = relationship(back_populates="brand")


class VehicleModel(Base):
    __tablename__ = "vehicle_models"
    __table_args__ = (UniqueConstraint("brand_id", "name", name="uq_vehicle_models_brand_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    body_type: Mapped[str | None] = mapped_column(String(40))  # sedán, SUV, pickup...

    brand: Mapped[Brand] = relationship(back_populates="models", lazy="joined")


class DataSource(Base):
    """Procedencia de un registro (requisito de Ingeniería de Datos)."""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[DataSourceKind] = mapped_column(pg_enum(DataSourceKind, "data_source_kind"))
    url: Mapped[str | None] = mapped_column(String(500))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
