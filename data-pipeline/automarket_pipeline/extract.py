"""Paso 1 · Extracción: scraping de catálogos oficiales -> raw/<run_id>/catalog_raw.csv"""
import pandas as pd

from automarket_pipeline.config import RunContext
from automarket_pipeline.http import PoliteClient
from automarket_pipeline.sources import RAW_COLUMNS, honda, mazda

SCRAPERS = {"honda_mx": honda.scrape, "mazda_mx": mazda.scrape}


def run(ctx: RunContext, log) -> pd.DataFrame:
    client = PoliteClient(ctx.raw_dir, log)
    rows: list[dict] = []
    try:
        for name, scrape in SCRAPERS.items():
            log.info("=== Extrayendo %s", name)
            found = scrape(client, log)
            log.info("%s: %d registros crudos", name, len(found))
            rows.extend(found)
    finally:
        client.write_manifest(ctx.evidence_dir / "manifest_descargas.json")
        client.close()

    df = pd.DataFrame(rows, columns=RAW_COLUMNS)
    out = ctx.raw_dir / "catalog_raw.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    log.info("Extracción terminada: %d registros -> %s", len(df), out)
    return df
