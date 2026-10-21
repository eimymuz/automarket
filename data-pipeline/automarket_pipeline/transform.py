"""Paso 2 · Transformación con Pandas: limpieza, validación, normalización y deduplicación.

Entrada:  raw/<run_id>/catalog_raw.csv   (texto tal como vino de la fuente)
Salida:   processed/catalog_clean.csv    (una fila por marca-modelo-año-versión-transmisión)
Evidencia: evidence/<run_id>/transform_report.json, duplicados.csv, rechazados.csv
"""
import json
import re
import unicodedata
from datetime import datetime

import pandas as pd

from automarket_pipeline.config import PROCESSED_DIR, RunContext, latest_run_with

BRANDS = {"honda": "Honda", "mazda": "Mazda"}
KEY = ["brand", "model", "year", "version", "transmission"]
MIN_YEAR, MAX_YEAR = 1990, datetime.now().year + 1

# Palabras que se escriben en mayúsculas aunque el resto vaya en formato título
_KEEP_UPPER = {"cx", "mx", "bt", "hr", "cr", "br", "wr", "suv", "rf", "mhev", "phev", "awd", "fwd"}


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def smart_title(text: str) -> str:
    """'MAZDA3 SEDÁN' -> 'Mazda3 Sedán'; 'MAZDA CX-30' -> 'Mazda CX-30'; 'hr-v' -> 'HR-V'."""
    words = []
    for word in str(text).split():
        if "-" in word and all(p.isalnum() for p in word.split("-")) and len(word) <= 6:
            words.append(word.upper())                     # CX-30, HR-V, BT-50
        elif _ascii(word) in _KEEP_UPPER:
            words.append(word.upper())
        elif word[:1].isdigit():
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def normalize_model(brand: str, model: str) -> str:
    """Quita la marca repetida: 'Mazda CX-30' -> 'CX-30' (pero conserva 'Mazda3')."""
    title = smart_title(model)
    prefix = f"{brand} "
    return title[len(prefix):] if title.lower().startswith(prefix.lower()) else title


def parse_price(raw) -> float | None:
    """'DESDE $ 403,900' -> 403900.0 ; '605900.00' -> 605900.0"""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(raw))
    return float(m.group(0).replace(",", "")) if m else None


def transmissions(raw) -> list[str]:
    """Una versión puede ofrecerse con varias transmisiones; se devuelve cada una."""
    found = []
    for item in str(raw or "").split("|"):
        text = _ascii(item)
        if "cvt" in text or "continuamente variable" in text:
            kind = "cvt"
        elif "automatic" in text:  # "automática ... con modo manual" sigue siendo automática
            kind = "automatica"
        elif "manual" in text:
            kind = "manual"
        else:
            continue  # "Sistema Eco Assist", "tracción delantera", etc.
        if kind not in found:
            found.append(kind)
    return found or [None]


def fuel(raw) -> str:
    text = _ascii(str(raw or ""))
    if re.search(r"phev|hibrid|hybrid|e:hev|mhev|e-skyactiv", text):
        return "hibrido"
    if "diesel" in text:
        return "diesel"
    if re.search(r"electric|\bev\b", text):
        return "electrico"
    return "gasolina"


def compact_engine(raw, hp) -> str:
    """'4 Cilindros en Línea, 2.0 Litros ... 150 hp' -> '2.0L 4 cil. 150 hp'"""
    text = "" if pd.isna(raw) else str(raw)
    parts = []
    disp = re.search(r"\b(\d\.\d)\s*(?:L\b|Litros|Turbo)", text, re.I)
    if disp:
        parts.append(f"{disp.group(1)}L")
    if re.search(r"turbo", text, re.I):
        parts.append("Turbo")
    cyl = re.search(r"(\d)\s*Cilindros", text, re.I)
    if cyl:
        parts.append(f"{cyl.group(1)} cil.")
    if pd.notna(hp) and str(hp).strip():
        parts.append(f"{int(float(hp))} hp")
    return " ".join(parts) if parts else re.sub(r"\s+", " ", text)[:80]


def normalize_version(raw) -> str:
    """'PRIME CVT' -> 'Prime'; 'Uniq CVT' -> 'Uniq'. La transmisión ya vive en su propia columna."""
    text = re.sub(r"\s+", " ", "" if pd.isna(raw) else str(raw)).strip()
    text = re.sub(r"\s+(CVT|MT|AT|TA|TM)$", "", text, flags=re.I)
    if text.isupper() and len(text) > 3:
        text = smart_title(text)
    return text or "Base"


def body_type(model: str, raw) -> str:
    text = _ascii(f"{model} {raw or ''}")
    if re.search(r"\b(cx|hr|cr|br)-|pilot|suv|camioneta", text):
        return "SUV"
    if re.search(r"odyssey|minivan", text):
        return "Minivan"
    if re.search(r"bt-50|pickup|ridgeline", text):
        return "Pickup"
    if re.search(r"hatchback|\bhb\b|fit", text):
        return "Hatchback"
    if re.search(r"mx-5|roadster|\brf\b", text):
        return "Convertible"
    return "Sedán"


def run(ctx: RunContext, log, raw_csv=None) -> pd.DataFrame:
    raw_csv = raw_csv or (ctx.raw_dir / "catalog_raw.csv")
    if not raw_csv.exists():
        raw_csv = latest_run_with("catalog_raw.csv")
    log.info("Transformando %s", raw_csv)
    raw = pd.read_csv(raw_csv, dtype=str, keep_default_na=False, na_values=[""])
    report: dict = {"input_file": str(raw_csv), "input_rows": len(raw)}

    # 1) Valores nulos en los datos crudos
    report["nulls_raw"] = {c: int(n) for c, n in raw.isna().sum().items() if n}

    # 2) Limpieza y normalización
    df = pd.DataFrame({
        "source": raw["source"],
        "source_url": raw["source_url"],
        "scraped_at": pd.to_datetime(raw["scraped_at"], utc=True, errors="coerce"),
        "brand": raw["brand_raw"].str.strip().str.lower().map(BRANDS),
        "year": pd.to_numeric(raw["year_raw"], errors="coerce").astype("Int64"),
        "version": raw["version_raw"].map(normalize_version),
        "price_mxn": raw["price_raw"].map(parse_price),
        "horsepower": pd.to_numeric(raw["horsepower_raw"], errors="coerce").astype("Int64"),
        "fuel_type": raw["fuel_raw"].map(fuel),
        "colors": raw["colors_raw"].fillna("").map(
            lambda s: " | ".join(smart_title(c.strip()) for c in s.split("|") if c.strip())
        ),
        "image_url": raw["image_url"],
        "_transmissions": raw["transmission_raw"].map(transmissions),
        "_model_raw": raw["model_raw"],
        "_engine_raw": raw["engine_raw"],
        "_body_raw": raw["body_type_raw"],
    })
    df["model"] = [normalize_model(b or "", m or "") for b, m in zip(df["brand"], df["_model_raw"])]
    df["engine"] = [compact_engine(e, h) for e, h in zip(df["_engine_raw"], df["horsepower"])]
    df["body_type"] = [body_type(m, b) for m, b in zip(df["model"], df["_body_raw"])]

    # Una versión con manual y automática se convierte en dos registros de catálogo
    df = df.explode("_transmissions").rename(columns={"_transmissions": "transmission"})
    report["rows_after_transmission_split"] = len(df)

    # 3) Validación de tipos y reglas de negocio -> rechazados con su motivo
    checks = {
        "marca_desconocida": df["brand"].isna(),
        "modelo_vacio": df["model"].str.strip() == "",
        "anio_invalido": df["year"].isna() | ~df["year"].between(MIN_YEAR, MAX_YEAR),
        "precio_invalido": df["price_mxn"].isna() | (df["price_mxn"] <= 0),
        "transmision_desconocida": df["transmission"].isna(),
        "motor_desconocido": df["engine"].str.strip() == "",
    }
    reasons = pd.Series("", index=df.index)
    for reason, mask in checks.items():
        reasons = reasons.where(~mask.fillna(True), reasons + reason + ";")
    rejected = df[reasons != ""].assign(motivo=reasons[reasons != ""])
    df = df[reasons == ""].copy()
    report["rejected"] = {k: int(v.fillna(True).sum()) for k, v in checks.items()}
    report["rejected_rows"] = len(rejected)

    # 4) Duplicados por llave natural (marca, modelo, año, versión, transmisión)
    dup_mask = df.duplicated(subset=KEY, keep="first")
    duplicates = df[df.duplicated(subset=KEY, keep=False)].sort_values(KEY)
    report["duplicates_removed"] = int(dup_mask.sum())
    df = df[~dup_mask]

    # 5) Salida ordenada y con tipos finales
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
    df["price_mxn"] = df["price_mxn"].round(2)
    df = df.sort_values(KEY).reset_index(drop=True)
    columns = ["brand", "model", "year", "version", "transmission", "fuel_type", "engine", "horsepower",
               "body_type", "price_mxn", "colors", "image_url", "source", "source_url", "scraped_at"]
    df = df[columns]

    report["output_rows"] = len(df)
    report["nulls_clean"] = {c: int(n) for c, n in df.isna().sum().items() if n}
    report["dtypes"] = {c: str(t) for c, t in df.dtypes.items()}
    report["by_brand"] = df["brand"].value_counts().to_dict()

    out = PROCESSED_DIR / "catalog_clean.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    df.to_csv(ctx.evidence_dir / "catalog_clean.csv", index=False, encoding="utf-8-sig")
    rejected.drop(columns=[c for c in rejected.columns if c.startswith("_")], errors="ignore") \
        .to_csv(ctx.evidence_dir / "rechazados.csv", index=False, encoding="utf-8-sig")
    duplicates.drop(columns=[c for c in duplicates.columns if c.startswith("_")], errors="ignore") \
        .to_csv(ctx.evidence_dir / "duplicados.csv", index=False, encoding="utf-8-sig")
    (ctx.evidence_dir / "transform_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log.info(
        "Transformación: %d crudos -> %d limpios (%d rechazados, %d duplicados eliminados)",
        report["input_rows"], len(df), len(rejected), report["duplicates_removed"],
    )
    return df
