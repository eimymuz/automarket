"""Rutas y parámetros del pipeline."""
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PIPELINE_DIR / "raw"
PROCESSED_DIR = PIPELINE_DIR / "processed"
EVIDENCE_DIR = PIPELINE_DIR / "evidence"
BACKEND_DIR = PIPELINE_DIR.parent / "backend"

# El scraper se identifica honestamente y respeta robots.txt
USER_AGENT = "AutoMarketBot/0.1 (proyecto escolar de Ingenieria de Datos; uso no comercial)"
REQUEST_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30.0

# Semilla fija: la generación de inventario es reproducible
RANDOM_SEED = 2026


@dataclass
class RunContext:
    """Datos de una ejecución: cada corrida guarda su HTML y sus evidencias en carpetas propias."""

    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    @property
    def raw_dir(self) -> Path:
        return RAW_DIR / self.run_id

    @property
    def evidence_dir(self) -> Path:
        return EVIDENCE_DIR / self.run_id

    def setup(self) -> logging.Logger:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

        log = logging.getLogger("pipeline")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
        for handler in (
            logging.FileHandler(self.evidence_dir / "pipeline.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ):
            handler.setFormatter(fmt)
            log.addHandler(handler)
        return log


def latest_run_with(filename: str) -> Path:
    """Devuelve el archivo más reciente con ese nombre dentro de raw/<run_id>/."""
    candidates = sorted(RAW_DIR.glob(f"*/{filename}"))
    if not candidates:
        raise FileNotFoundError(f"No hay ninguna corrida previa con {filename}; ejecuta primero 'extract'.")
    return candidates[-1]
