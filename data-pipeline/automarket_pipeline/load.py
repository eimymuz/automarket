"""Paso 4 · Carga en PostgreSQL, en una sola transacción y de forma idempotente.

Reutiliza los modelos y la conexión del backend (backend/app), así el pipeline y la API
comparten exactamente el mismo esquema. Volver a ejecutar la carga no duplica vehículos:
el folio (stock_number) es la llave y los existentes se omiten (ON CONFLICT DO NOTHING).
"""
import sys
from datetime import datetime, timezone

import pandas as pd

from automarket_pipeline.config import BACKEND_DIR, PROCESSED_DIR, RunContext

sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.models import Brand, DataSource, OperationHistory, Vehicle, VehicleImage, VehicleModel  # noqa: E402
from app.models.enums import DataSourceKind, FuelType, OperationSource, Transmission  # noqa: E402

SOURCE_INFO = {
    "honda_mx": ("Honda México", "https://www.honda.mx"),
    "mazda_mx": ("Mazda México", "https://www.mazda.mx"),
}


def _data_source(db: Session, source: str, kind: str, collected_at, run_id: str) -> int:
    label, url = SOURCE_INFO[source]
    if kind == "real":
        name = f"{label} · catálogo oficial (scraping)"
        notes = f"Precio y especificaciones de autos nuevos tomados de {url}. Corrida {run_id}."
    else:
        name = f"{label} · seminuevos derivados del catálogo"
        notes = (f"Unidades seminuevas generadas a partir del catálogo oficial de {url}: año, km y precio "
                 f"calculados con depreciación fija (ver generate.py). Corrida {run_id}.")
    stmt = insert(DataSource).values(
        name=name, kind=DataSourceKind(kind), url=url, collected_at=collected_at, notes=notes,
    ).on_conflict_do_update(index_elements=["name"], set_={"collected_at": collected_at, "notes": notes})
    db.execute(stmt)
    return db.scalar(select(DataSource.id).where(DataSource.name == name))


def run(ctx: RunContext, log, inventory: pd.DataFrame | None = None) -> dict:
    if inventory is None:
        inventory = pd.read_csv(PROCESSED_DIR / "inventory.csv", encoding="utf-8-sig")
    inventory = inventory.astype(object).where(inventory.notna(), None)
    stats = {"vehicles_inserted": 0, "vehicles_skipped": 0, "images_inserted": 0}

    with Session(engine) as db, db.begin():
        # Marcas y modelos (upsert)
        brand_ids, model_ids, source_ids = {}, {}, {}
        for brand in sorted(inventory["brand"].unique()):
            db.execute(insert(Brand).values(name=brand).on_conflict_do_nothing(index_elements=["name"]))
            brand_ids[brand] = db.scalar(select(Brand.id).where(Brand.name == brand))
        for (brand, model), grp in inventory.groupby(["brand", "model"]):
            db.execute(
                insert(VehicleModel)
                .values(brand_id=brand_ids[brand], name=model, body_type=grp["body_type"].iloc[0])
                .on_conflict_do_nothing(constraint="uq_vehicle_models_brand_name")
            )
            model_ids[(brand, model)] = db.scalar(
                select(VehicleModel.id).where(VehicleModel.brand_id == brand_ids[brand], VehicleModel.name == model)
            )
        for (source, kind), grp in inventory.groupby(["source", "data_kind"]):
            collected = pd.to_datetime(grp["scraped_at"], utc=True).min().to_pydatetime()
            source_ids[(source, kind)] = _data_source(db, source, kind, collected, ctx.run_id)

        # Vehículos
        for row in inventory.itertuples(index=False):
            vehicle_id = db.scalar(
                insert(Vehicle)
                .values(
                    stock_number=row.stock_number, model_id=model_ids[(row.brand, row.model)],
                    year=int(row.year), version=row.version, price_mxn=row.price_mxn,
                    mileage_km=int(row.mileage_km), color=row.color,
                    transmission=Transmission(row.transmission), fuel_type=FuelType(row.fuel_type),
                    engine=row.engine, description=row.description,
                    data_source_id=source_ids[(row.source, row.data_kind)],
                )
                .on_conflict_do_nothing(index_elements=["stock_number"])
                .returning(Vehicle.id)
            )
            if vehicle_id is None:
                stats["vehicles_skipped"] += 1
                continue
            stats["vehicles_inserted"] += 1
            if row.image_url:
                db.add(VehicleImage(vehicle_id=vehicle_id, url=row.image_url, is_primary=True, position=0))
                stats["images_inserted"] += 1
            db.add(OperationHistory(
                vehicle_id=vehicle_id, operation="carga_inicial", source=OperationSource.PIPELINE,
                to_status="disponible",
                details={"run_id": ctx.run_id, "stock_number": row.stock_number,
                         "data_kind": row.data_kind, "source_url": row.source_url},
            ))

    stats["loaded_at"] = datetime.now(timezone.utc).isoformat()
    log.info("Carga: %(vehicles_inserted)d insertados, %(vehicles_skipped)d ya existían, "
             "%(images_inserted)d imágenes", stats)
    return stats
