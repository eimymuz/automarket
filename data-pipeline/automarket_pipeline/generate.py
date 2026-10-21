"""Paso 3 · Generación del inventario de la agencia a partir del catálogo limpio.

Cada versión del catálogo oficial produce:
  - 1 unidad nueva (0 km, precio oficial)            -> data_kind = "real"
  - 1-2 unidades seminuevas (1-4 años, km y precio
    depreciado calculados con reglas fijas)          -> data_kind = "referencia"

La semilla es fija, así que el mismo catálogo siempre produce el mismo inventario.
Salida: processed/inventory.csv
"""
import hashlib

import numpy as np
import pandas as pd

from automarket_pipeline.config import PROCESSED_DIR, RANDOM_SEED, RunContext

ANNUAL_DEPRECIATION = 0.12   # 12 % por año
KM_PER_YEAR_MEAN, KM_PER_YEAR_SD = 15_000, 4_000
MAX_KM_PENALTY = 0.15        # el kilometraje resta hasta 15 % adicional
TRANSMISSION_LABEL = {"cvt": "CVT", "automatica": "automática", "manual": "manual"}


def stock_number(*key) -> str:
    """Folio estable derivado de la llave natural: el mismo vehículo conserva su folio entre corridas."""
    digest = hashlib.sha1("|".join(map(str, key)).encode()).hexdigest()[:8].upper()
    return f"AM-{digest}"


def used_price(msrp: float, age: int, km: int) -> float:
    price = msrp * (1 - ANNUAL_DEPRECIATION) ** age * (1 - min(km / 400_000, MAX_KM_PENALTY))
    return float(round(price / 500) * 500)  # precios "de lista": múltiplos de $500


def describe(row, year: int, km: int, condition: str) -> str:
    trans = TRANSMISSION_LABEL.get(row.transmission, row.transmission)
    base = f"{row.brand} {row.model} {row.version} {year}, motor {row.engine}, transmisión {trans}."
    if condition == "nuevo":
        return f"{base} Unidad nueva, precio de lista del catálogo oficial {row.brand} México."
    return f"{base} Seminuevo con {km:,} km. Precio estimado a partir del catálogo oficial."


def run(ctx: RunContext, log, catalog: pd.DataFrame | None = None) -> pd.DataFrame:
    if catalog is None:
        catalog = pd.read_csv(PROCESSED_DIR / "catalog_clean.csv", encoding="utf-8-sig")
    rng = np.random.default_rng(RANDOM_SEED)
    units = []

    for row in catalog.itertuples(index=False):
        colors = [c.strip() for c in str(row.colors).split("|") if c.strip() and c.strip() != "nan"]
        key = (row.brand, row.model, row.year, row.version, row.transmission)

        def unit(idx: int, year: int, km: int, price: float, kind: str, condition: str) -> dict:
            return {
                "stock_number": stock_number(*key, idx),
                "brand": row.brand, "model": row.model, "body_type": row.body_type,
                "year": year, "version": row.version, "price_mxn": price, "mileage_km": km,
                "color": rng.choice(colors) if colors else "Sin especificar",
                "transmission": row.transmission, "fuel_type": row.fuel_type, "engine": row.engine,
                "description": describe(row, year, km, condition),
                "image_url": row.image_url, "data_kind": kind, "condition": condition,
                "catalog_price_mxn": row.price_mxn, "source": row.source,
                "source_url": row.source_url, "scraped_at": row.scraped_at,
            }

        units.append(unit(0, int(row.year), 0, float(row.price_mxn), "real", "nuevo"))
        ages = rng.choice([1, 2, 3, 4], size=int(rng.integers(1, 3)), replace=False)
        for i, age in enumerate(sorted(ages), start=1):
            km = int(max(1_000, rng.normal(KM_PER_YEAR_MEAN, KM_PER_YEAR_SD) * age) // 100 * 100)
            units.append(unit(i, int(row.year) - int(age), km, used_price(row.price_mxn, int(age), km),
                              "referencia", "seminuevo"))

    inv = pd.DataFrame(units)
    assert inv["stock_number"].is_unique, "Colisión de folios"
    inv.to_csv(PROCESSED_DIR / "inventory.csv", index=False, encoding="utf-8-sig")
    inv.to_csv(ctx.evidence_dir / "inventory.csv", index=False, encoding="utf-8-sig")
    log.info(
        "Inventario generado: %d unidades (%s)", len(inv),
        ", ".join(f"{k}={v}" for k, v in inv["data_kind"].value_counts().items()),
    )
    return inv
