"""Mazda México (https://www.mazda.mx).

robots.txt solo bloquea herramientas internas (/services/, /herramientas-de-compra/apartado/, ...);
las páginas de vehículos están permitidas.
- /vehiculos/<modelo>/versiones incluye <script id="comparaTrimmer"> (JSON) con versiones,
  precio "desde" y especificaciones por versión.
- /vehiculos/<modelo> incluye la paleta de colores (data-analytics-link-description).
"""
import ast
import html
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone

from automarket_pipeline.http import PoliteClient
from automarket_pipeline.sources import sitemap_urls, strip_html

BASE_URL = "https://www.mazda.mx"
SOURCE = "mazda_mx"
VERSIONS_URL_RE = re.compile(r"^https://www\.mazda\.mx/vehiculos/([a-z0-9\-]+)/(?:compara-)?versiones/?$")
MODEL_PATH_RE = re.compile(r"^https://www\.mazda\.mx/vehiculos/([a-z0-9\-]+)(?:/|$)")
TRIMMER_RE = re.compile(r'<script id="comparaTrimmer"[^>]*>(.*?)</script>', re.S)
VEHICLE_DATA_RE = re.compile(r'<script id="vehicle-data"[^>]*>(.*?)</script>', re.S)
COLOR_RE = re.compile(r'<li[^>]*\bdata-color="[^"]+"[^>]*data-analytics-link-description="([^"]+)"')


def discover_version_urls(sitemap_xml: str) -> dict[str, str]:
    """{slug: url_de_versiones}. Si hay /versiones y /compara-versiones, gana /versiones.

    El sitemap no lista la página de versiones de todos los modelos (p. ej. CX-50), así que
    para cada modelo sin ella se intenta la ruta estándar /vehiculos/<modelo>/versiones.
    """
    urls = sitemap_urls(sitemap_xml)
    found: dict[str, str] = {}
    for url in urls:
        m = VERSIONS_URL_RE.match(url)
        if m and (m.group(1) not in found or url.endswith("/versiones")):
            found[m.group(1)] = url
    for url in urls:
        m = MODEL_PATH_RE.match(url)
        if m and m.group(1) not in found:
            found[m.group(1)] = f"{BASE_URL}/vehiculos/{m.group(1)}/versiones"
    return found


def parse_colors(model_html: str) -> list[str]:
    return list(dict.fromkeys(strip_html(c) for c in COLOR_RE.findall(model_html or "")))


def _plain(text) -> str:
    """'Transmisión automática' -> 'transmision automatica' (minúsculas, sin acentos)."""
    return unicodedata.normalize("NFKD", strip_html(text)).encode("ascii", "ignore").decode().lower()


def _values(entry: dict) -> list[str]:
    raw = entry.get("values")
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)  # viene como "['2.5L', '2.0L']"
        except (ValueError, SyntaxError):
            return []
    return [strip_html(v) for v in raw or []]


def parse_versions_page(page_html: str, url: str, colors: list[str], scraped_at: str) -> list[dict]:
    match = TRIMMER_RE.search(page_html)
    if not match:
        return []
    data = json.loads(match.group(1))
    headers = (data.get("headers") or {}).get("carHeaders") or []
    image = (data.get("headers") or {}).get("image") or ""

    year = ""
    vd = VEHICLE_DATA_RE.search(page_html)
    if vd:
        year = str(json.loads(html.unescape(vd.group(1))).get("Year", ""))

    entries = [
        entry
        for container in data.get("containers") or []
        for category in container.get("categories") or []
        for entry in category.get("entries") or []
    ]

    # Los entryId no son consistentes entre modelos (TIPO_DE_MOTOR, TIPO_DE_MOTOR_SM, ...);
    # se identifica cada especificación por su nombre visible.
    named = [(_plain(e.get("entryName")), e) for e in entries]

    def entry_values(prefix: str) -> list[str]:
        e = next((e for name, e in named if name.startswith(prefix)), None)
        return _values(e) if e else []

    engines = entry_values("tipo de motor")
    power = entry_values("potencia")
    transmissions = [(strip_html(e.get("entryName")), _values(e)) for name, e in named
                     if name.startswith("transmision")]

    rows = []
    for i, header in enumerate(headers):
        def at(values: list[str]) -> str:
            return values[i] if i < len(values) else ""

        engine = at(engines)
        trans = [name for name, vals in transmissions if at(vals).lower() == "true"]
        hp = re.match(r"\s*(\d{2,4})", at(power))
        rows.append({
            "source": SOURCE,
            "source_url": url,
            "scraped_at": scraped_at,
            "brand_raw": "MAZDA",
            "model_raw": strip_html(header.get("model")),
            "year_raw": year,
            "version_raw": strip_html(header.get("version")),
            "price_raw": strip_html(header.get("startPrice")),
            "engine_raw": engine,
            "horsepower_raw": hp.group(1) if hp else "",
            "transmission_raw": " | ".join(trans),
            "fuel_raw": " ".join([strip_html(header.get("model")), strip_html(header.get("version")), engine]),
            "body_type_raw": "",
            "colors_raw": " | ".join(colors),
            "image_url": (BASE_URL + image) if image.startswith("/") else image,
        })
    return rows


def scrape(client: PoliteClient, log: logging.Logger) -> list[dict]:
    sitemap = client.get(f"{BASE_URL}/sitemap.xml", f"{SOURCE}/sitemap.xml")
    if not sitemap:
        log.error("Mazda: no se pudo leer el sitemap")
        return []
    version_urls = discover_version_urls(sitemap)
    log.info("Mazda: %d modelos con página de versiones", len(version_urls))

    rows: list[dict] = []
    for slug, url in version_urls.items():
        model_page = client.get(f"{BASE_URL}/vehiculos/{slug}", f"{SOURCE}/{slug}.html") or ""
        page = client.get(url, f"{SOURCE}/{slug}_versiones.html")
        if not page:
            continue
        found = parse_versions_page(page, url, parse_colors(model_page), datetime.now(timezone.utc).isoformat())
        log.info("Mazda %-18s -> %d versiones", slug, len(found))
        rows.extend(found)
    return rows
