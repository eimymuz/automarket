"""Paso 5 · Estadísticas del inventario, leídas directamente de PostgreSQL con Pandas."""
import sys

import pandas as pd

from automarket_pipeline.config import BACKEND_DIR, RunContext

sys.path.insert(0, str(BACKEND_DIR))
from app.db.session import engine  # noqa: E402

QUERY = """
SELECT v.stock_number, b.name AS brand, m.name AS model, m.body_type, v.year, v.version,
       v.price_mxn::float AS price_mxn, v.mileage_km, v.transmission::text, v.fuel_type::text,
       v.status::text, ds.kind::text AS data_kind
FROM vehicles v
JOIN vehicle_models m ON m.id = v.model_id
JOIN brands b ON b.id = m.brand_id
LEFT JOIN data_sources ds ON ds.id = v.data_source_id
WHERE v.deleted_at IS NULL
"""


def _md_table(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:,.0f}" if isinstance(v, float) else str(v) for v in row) + " |")
    return "\n".join(lines)


def run(ctx: RunContext, log) -> dict:
    df = pd.read_sql(QUERY, engine)
    by_brand = (df.groupby("brand")
                  .agg(unidades=("stock_number", "count"), precio_promedio=("price_mxn", "mean"),
                       precio_min=("price_mxn", "min"), precio_max=("price_mxn", "max"))
                  .reset_index())
    sections = {
        "Por marca": by_brand,
        "Por estado": df["status"].value_counts().rename_axis("estado").reset_index(name="unidades"),
        "Por procedencia del dato": df["data_kind"].value_counts().rename_axis("tipo").reset_index(name="unidades"),
        "Por carrocería": df["body_type"].value_counts().rename_axis("carroceria").reset_index(name="unidades"),
        "Por combustible": df["fuel_type"].value_counts().rename_axis("combustible").reset_index(name="unidades"),
        "Por transmisión": df["transmission"].value_counts().rename_axis("transmision").reset_index(name="unidades"),
        "Por año": df["year"].value_counts().sort_index().rename_axis("anio").reset_index(name="unidades"),
        "Rangos de precio (MXN)": pd.cut(
            df["price_mxn"], bins=[0, 300_000, 450_000, 600_000, 800_000, 1_000_000, float("inf")],
            labels=["< 300 mil", "300-450 mil", "450-600 mil", "600-800 mil", "800 mil-1 M", "> 1 M"],
        ).value_counts(sort=False).rename_axis("rango").reset_index(name="unidades"),
    }

    md = [f"# Estadísticas del inventario · corrida {ctx.run_id}", "",
          f"- **Total de vehículos activos:** {len(df)}",
          f"- **Marcas:** {df['brand'].nunique()} · **Modelos:** {df['model'].nunique()}",
          f"- **Precio promedio:** ${df['price_mxn'].mean():,.0f} MXN · "
          f"**mediana:** ${df['price_mxn'].median():,.0f} MXN",
          f"- **Kilometraje promedio (seminuevos):** {df.loc[df['mileage_km'] > 0, 'mileage_km'].mean():,.0f} km", ""]
    for title, table in sections.items():
        md += [f"## {title}", "", _md_table(table), ""]
    (ctx.evidence_dir / "estadisticas.md").write_text("\n".join(md), encoding="utf-8")
    df.to_csv(ctx.evidence_dir / "inventario_en_bd.csv", index=False, encoding="utf-8-sig")

    log.info("Estadísticas: %d vehículos en BD, %d marcas, %d modelos",
             len(df), df["brand"].nunique(), df["model"].nunique())
    return {"total": len(df), "by_brand": by_brand.set_index("brand")["unidades"].to_dict()}
