"""Ejecuta el pipeline de AutoMarket.

Uso (desde data-pipeline/, con el entorno virtual del backend):
    python run_pipeline.py                     # todos los pasos
    python run_pipeline.py --steps transform,generate,load,stats   # sin volver a descargar
"""
import argparse
import json
import time

from automarket_pipeline import extract, generate, load, stats, transform
from automarket_pipeline.config import RunContext

STEPS = ["extract", "transform", "generate", "load", "stats"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de datos de AutoMarket")
    parser.add_argument("--steps", default=",".join(STEPS), help=f"Pasos separados por coma: {STEPS}")
    args = parser.parse_args()
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = set(steps) - set(STEPS)
    if unknown:
        parser.error(f"Pasos desconocidos: {unknown}")

    ctx = RunContext()
    log = ctx.setup()
    log.info("Corrida %s · pasos: %s", ctx.run_id, ", ".join(steps))
    summary: dict = {"run_id": ctx.run_id, "steps": {}}
    catalog = inventory = None

    for step in steps:
        start = time.perf_counter()
        if step == "extract":
            result = {"raw_rows": len(extract.run(ctx, log))}
        elif step == "transform":
            catalog = transform.run(ctx, log)
            result = {"catalog_rows": len(catalog)}
        elif step == "generate":
            inventory = generate.run(ctx, log, catalog)
            result = {"inventory_rows": len(inventory)}
        elif step == "load":
            result = load.run(ctx, log, inventory)
        else:
            result = stats.run(ctx, log)
        result["seconds"] = round(time.perf_counter() - start, 2)
        summary["steps"][step] = result

    (ctx.evidence_dir / "resumen.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log.info("Listo. Evidencias en %s", ctx.evidence_dir)


if __name__ == "__main__":
    main()
