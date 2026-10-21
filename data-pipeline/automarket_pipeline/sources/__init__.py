"""Extractores por fuente. Todos devuelven filas con el mismo esquema "crudo" (texto tal como viene)."""
import html
import re

RAW_COLUMNS = [
    "source", "source_url", "scraped_at", "brand_raw", "model_raw", "year_raw", "version_raw",
    "price_raw", "engine_raw", "horsepower_raw", "transmission_raw", "fuel_raw", "body_type_raw",
    "colors_raw", "image_url",
]

_TAG_RE = re.compile(r"<[^>]+>")
_SUP_RE = re.compile(r"<sup\b.*?</sup>", re.S | re.I)  # notas al pie ("¹") pegadas a los precios
_WS_RE = re.compile(r"\s+")


def strip_html(value: str | None) -> str:
    if value is None:
        return ""
    text = _SUP_RE.sub("", str(value))
    text = html.unescape(_TAG_RE.sub(" ", text)).replace("\xa0", " ")
    return _WS_RE.sub(" ", text).strip()


def sitemap_urls(xml_text: str) -> list[str]:
    return [html.unescape(u).strip() for u in re.findall(r"<loc>([^<]+)</loc>", xml_text)]
