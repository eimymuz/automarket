import base64

from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import requires_db

pytestmark = requires_db

NEW_VEHICLE = {
    "brand": "MarcaPrueba", "model": "Nuevo Modelo", "body_type": "Sedán", "year": 2024, "version": "Sport",
    "price_mxn": "389900.00", "mileage_km": 25000, "color": "Azul", "transmission": "manual",
    "fuel_type": "gasolina", "engine": "1.6L 120 hp", "description": "Registrado desde la prueba",
}
# PNG de 1x1 píxel
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def test_catalogo_publico_con_filtros(client, make_vehicle):
    barato = make_vehicle(price_mxn=200000, year=2020, color="Verde Prueba")
    make_vehicle(price_mxn=900000, year=2025)

    r = client.get("/api/v1/vehicles", params={"brand": "MarcaPrueba", "price_max": 300000})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["items"][0]["id"] == str(barato.id)
    assert body["items"][0]["brand"] == "MarcaPrueba" and body["items"][0]["status"] == "disponible"

    r = client.get("/api/v1/vehicles", params={"q": "verde prueba"})
    assert [v["id"] for v in r.json()["items"]] == [str(barato.id)]

    r = client.get("/api/v1/vehicles", params={"brand": "MarcaPrueba", "sort": "price_desc"})
    precios = [v["price_mxn"] for v in r.json()["items"]]
    assert precios == sorted(precios, reverse=True)


def test_filtros_invalidos(client):
    assert client.get("/api/v1/vehicles", params={"page_size": 500}).status_code == 422
    assert client.get("/api/v1/vehicles", params={"status": "robado"}).status_code == 422


def test_vehiculo_inexistente(client):
    r = client.get("/api/v1/vehicles/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["code"] == "vehicle_not_found"


def test_admin_registra_vehiculo_y_se_publica_evento(client, admin, published):
    _, headers = admin
    r = client.post("/api/v1/vehicles", json=NEW_VEHICLE, headers=headers)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["stock_number"].startswith("AM-") and v["price_mxn"] == 389900.0 and v["status"] == "disponible"
    assert [e["type"] for e in published] == ["vehicle.created"]
    assert client.get(f"/api/v1/vehicles/{v['id']}").status_code == 200  # la web ya lo ve


def test_validacion_de_vehiculo(client, admin):
    _, headers = admin
    r = client.post("/api/v1/vehicles", headers=headers,
                    json=NEW_VEHICLE | {"price_mxn": "-5", "year": 1800, "transmission": "cohete"})
    assert r.status_code == 422
    assert {e["loc"][-1] for e in r.json()["detail"]} == {"price_mxn", "year", "transmission"}


def test_cambio_de_precio_historial_auditoria_y_evento(client, db, admin, make_vehicle, published):
    user, headers = admin
    v = make_vehicle()
    r = client.patch(f"/api/v1/vehicles/{v.id}", headers=headers,
                     json={"row_version": v.row_version, "price_mxn": "429900.00"})
    assert r.status_code == 200, r.text
    assert r.json()["price_mxn"] == 429900.0 and r.json()["row_version"] == 2

    hist = client.get(f"/api/v1/vehicles/{v.id}/history", headers=headers).json()
    assert hist[0]["operation"] == "precio_actualizado" and hist[0]["source"] == "desktop"
    assert hist[0]["details"]["cambios"]["price_mxn"] == {"antes": 450000.0, "despues": 429900.0}

    audit = db.scalars(select(AuditLog).where(AuditLog.table_name == "vehicles",
                                              AuditLog.record_id == str(v.id), AuditLog.action == "UPDATE")).all()
    assert audit and audit[-1].changed_by == str(user.id)
    assert published[-1]["type"] == "vehicle.updated" and published[-1]["data"]["changed"] == ["price_mxn"]


def test_edicion_simultanea_detectada(client, admin, make_vehicle):
    _, headers = admin
    v = make_vehicle()
    version_leida = v.row_version
    assert client.patch(f"/api/v1/vehicles/{v.id}", headers=headers,
                        json={"row_version": version_leida, "color": "Negro"}).status_code == 200
    # Otro administrador intenta guardar con la versión vieja
    r = client.patch(f"/api/v1/vehicles/{v.id}", headers=headers,
                     json={"row_version": version_leida, "color": "Blanco"})
    assert r.status_code == 409 and r.json()["code"] == "version_conflict"


def test_baja_controlada(client, admin, customer, make_vehicle):
    _, admin_h = admin
    _, client_h = customer
    v = make_vehicle()
    client.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(v.id)})
    r = client.delete(f"/api/v1/vehicles/{v.id}", headers=admin_h)
    assert r.status_code == 409 and r.json()["code"] == "vehicle_not_deletable"

    libre = make_vehicle()
    assert client.delete(f"/api/v1/vehicles/{libre.id}", headers=admin_h).status_code == 204
    assert client.get(f"/api/v1/vehicles/{libre.id}").status_code == 404


def test_fotografias(client, admin, make_vehicle, tmp_path):
    _, headers = admin
    v = make_vehicle()
    r = client.post(f"/api/v1/vehicles/{v.id}/images", headers=headers,
                    files={"file": ("auto.png", PNG, "image/png")})
    assert r.status_code == 201, r.text
    img = r.json()["images"][0]
    assert img["is_primary"] and img["url"].startswith("/media/vehicles/")
    assert (tmp_path / img["url"].removeprefix("/media/")).exists()

    r = client.post(f"/api/v1/vehicles/{v.id}/images", headers=headers,
                    files={"file": ("auto2.png", PNG, "image/png")})
    second = r.json()["images"][1]
    assert not second["is_primary"]
    r = client.post(f"/api/v1/vehicles/{v.id}/images/{second['id']}/primary", headers=headers)
    assert [i["is_primary"] for i in r.json()["images"]] == [False, True]

    r = client.delete(f"/api/v1/vehicles/{v.id}/images/{second['id']}", headers=headers)
    assert [i["is_primary"] for i in r.json()["images"]] == [True]


def test_archivo_que_no_es_imagen(client, admin, make_vehicle):
    _, headers = admin
    v = make_vehicle()
    r = client.post(f"/api/v1/vehicles/{v.id}/images", headers=headers,
                    files={"file": ("virus.png", b"MZ\x90\x00 no soy png", "image/png")})
    assert r.status_code == 400 and r.json()["code"] == "invalid_image"
