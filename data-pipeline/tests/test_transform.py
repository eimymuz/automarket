"""Pruebas de las reglas de limpieza y normalización (no requieren red ni base de datos)."""
import pytest

from automarket_pipeline.generate import stock_number, used_price
from automarket_pipeline.sources import strip_html
from automarket_pipeline.transform import (
    body_type, compact_engine, fuel, normalize_model, normalize_version, parse_price, transmissions,
)


@pytest.mark.parametrize("raw, expected", [
    ("DESDE $ 403,900", 403900.0),
    ("605900.00", 605900.0),
    ("$1,011,900", 1011900.0),
    ("", None),
    (None, None),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_strip_html_quita_notas_al_pie():
    raw = '<p><span>DESDE&nbsp;</span>$403,900<sup class="x">1</sup></p>'
    assert strip_html(raw) == "DESDE $403,900"


@pytest.mark.parametrize("brand, raw, expected", [
    ("Mazda", "MAZDA3 SEDÁN", "Mazda3 Sedán"),
    ("Mazda", "MAZDA CX-30", "CX-30"),
    ("Honda", "HR-V", "HR-V"),
    ("Honda", "Civic", "Civic"),
])
def test_normalize_model(brand, raw, expected):
    assert normalize_model(brand, raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("PRIME CVT", "Prime"),
    ("Uniq CVT", "Uniq"),
    ("i Grand Touring", "i Grand Touring"),
    ("", "Base"),
])
def test_normalize_version(raw, expected):
    assert normalize_version(raw) == expected


def test_transmisiones():
    assert transmissions("Sistema Eco Assist® | Transmisión Continuamente Variable (CVT)") == ["cvt"]
    assert transmissions("Transmisión automática SKYACTIV-Drive 6 velocidades con modo manual") == ["automatica"]
    assert transmissions("Transmisión manual MT 6 vel. | Transmisión automática con modo manual") == ["manual", "automatica"]
    assert transmissions("") == [None]


@pytest.mark.parametrize("raw, expected", [
    ("Mazda3 i Grand Touring MHEV 2.0L e-SKYACTIV-G", "hibrido"),
    ("BT-50 Signature 3.0L Turbo diésel", "diesel"),
    ("CR-V e:HEV 2.0L", "hibrido"),
    ("Civic i-Style 2.0 Litros", "gasolina"),
])
def test_combustible(raw, expected):
    assert fuel(raw) == expected


def test_motor_compacto():
    assert compact_engine("4 Cilindros en Línea, 2.0 Litros de 16 válvulas 150 hp", 150) == "2.0L 4 cil. 150 hp"
    assert compact_engine("2.5 Turbo SKYACTIV®-G", 227) == "2.5L Turbo 227 hp"
    assert compact_engine(float("nan"), None) == ""


def test_carroceria():
    assert body_type("CX-30", "") == "SUV"
    assert body_type("Mazda3 Hatchback", "") == "Hatchback"
    assert body_type("Odyssey", "Autos") == "Minivan"
    assert body_type("BT-50", "") == "Pickup"


def test_folio_estable_y_precio_depreciado():
    assert stock_number("Honda", "Civic", 2026, "i-Style", "cvt", 0) == \
        stock_number("Honda", "Civic", 2026, "i-Style", "cvt", 0)
    assert stock_number("Honda", "Civic", 2026, "i-Style", "cvt", 0).startswith("AM-")
    price = used_price(600_000, age=2, km=30_000)
    assert price % 500 == 0 and 400_000 < price < 600_000
