"""Honda México (https://www.honda.mx).

robots.txt: "User-agent: * / Disallow:" -> se permite el rastreo completo.
Cada página /autos/<modelo> incluye los datos del modelo como JSON en el atributo
Vue `:model="..."`: versiones, precio, especificaciones, colores e imágenes.
"""
import html
import json
import logging
import re
from datetime import datetime, timezone

from automarket_pipeline.http import PoliteClient
from automarket_pipeline.sources import sitemap_urls, strip_html

BASE_URL = "https://www.honda.mx"
SOURCE = "honda_mx"
MODEL_URL_RE = re.compile(r"^https://www\.honda\.mx/autos/([a-z0-9\-]+)/?$")
NOT_MODELS = {"mantenimiento"}
MODEL_ATTR_RE = re.compile(r':(?:model|product)="([^"]+)"')


def discover_model_urls(sitemap_xml: str) -> list[str]:
    urls = []
    for url in sitemap_urls(sitemap_xml):
        m = MODEL_URL_RE.match(url)
        if m and m.group(1) not in NOT_MODELS and url not in urls:
            urls.append(url)
    return urls


def _absolute(path: str | None) -> str:
    if not path or path == "#":
        return ""
    return path if path.startswith("http") else BASE_URL + path


def _subspecs(version: dict) -> dict[str, list[tuple[str, str]]]:
    """{'TRANSMISIÓN': [(nombre, valor), ...], ...}"""
    out: dict[str, list[tuple[str, str]]] = {}
    for spec in (version.get("specs") or {}).get("specs") or []:
        section = strip_html(spec.get("name")).upper()
        out[section] = [
            (strip_html(s.get("name")), strip_html(str(s.get("value"))))
            for s in spec.get("subspecs") or []
        ]
    return out


def parse_model_page(page_html: str, url: str, scraped_at: str) -> list[dict]:
    match = MODEL_ATTR_RE.search(page_html)
    if not match:
        return []
    data = json.loads(html.unescape(match.group(1)))
    category = strip_html((data.get("category_product") or {}).get("name"))

    rows = []
    for version in data.get("product_versions") or []:
        specs = _subspecs(version)
        engine = next(
            (value for section, items in specs.items() if "INGENIER" in section or "MOTOR" in section
             for name, value in items if name.lower().startswith(("motor", "tren motriz"))),
            "",
        )
        transmission = [
            name for section, items in specs.items() if "TRANSMISI" in section
            for name, value in items if value.lower() == "true"
        ]
        card = (version.get("specs") or {}).get("versionCard") or {}
        configurator = version.get("configurator") or {}
        colors = [
            strip_html(c["color"]["name"])
            for c in configurator.get("exterior_colors") or []
            if c.get("color") and c["color"].get("name")
        ]
        price = (version.get("quote_product") or {}).get("price")
        hp = re.search(r"(\d{2,4})\s*hp", engine, re.I)

        rows.append({
            "source": SOURCE,
            "source_url": url,
            "scraped_at": scraped_at,
            "brand_raw": "Honda",
            "model_raw": strip_html(data.get("name")),
            "year_raw": str(version.get("year") or data.get("year") or ""),
            "version_raw": strip_html(version.get("name")),
            "price_raw": "" if price is None else str(price),
            "engine_raw": engine,
            "horsepower_raw": hp.group(1) if hp else "",
            "transmission_raw": " | ".join(transmission),
            "fuel_raw": " ".join([strip_html(data.get("name")), strip_html(version.get("name")), engine]),
            "body_type_raw": category,
            "colors_raw": " | ".join(dict.fromkeys(colors)),
            "image_url": _absolute(card.get("versionPicture")),
        })
    return rows


def scrape(client: PoliteClient, log: logging.Logger) -> list[dict]:
    sitemap = client.get(f"{BASE_URL}/sitemap.xml", f"{SOURCE}/sitemap.xml")
    if not sitemap:
        log.error("Honda: no se pudo leer el sitemap")
        return []
    urls = discover_model_urls(sitemap)
    log.info("Honda: %d páginas de modelo en el sitemap", len(urls))

    rows: list[dict] = []
    for url in urls:
        slug = MODEL_URL_RE.match(url).group(1)
        page = client.get(url, f"{SOURCE}/{slug}.html")
        if not page:
            continue
        found = parse_model_page(page, url, datetime.now(timezone.utc).isoformat())
        log.info("Honda %-10s -> %d versiones", slug, len(found))
        rows.extend(found)
    return rows
