"""Flujo completo de reservas, compras simuladas y ventas entre la web (cliente) y AutoMarket.exe (admin)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.models import Reservation, Sale
from app.services.commerce import expire_reservations
from tests.conftest import requires_db

pytestmark = requires_db
WEB = {"X-Client-App": "web"}


def status_of(client, vehicle_id) -> str:
    return client.get(f"/api/v1/vehicles/{vehicle_id}").json()["status"]


def test_flujo_completo_web_reserva_compra_y_admin_confirma(client, db, admin, customer, published, make_vehicle):
    _, admin_h = admin
    _, client_h = customer
    v = make_vehicle()

    # 1. Cliente reserva desde la web -> AutoMarket.exe ve "reservado"
    r = client.post("/api/v1/reservations", headers=client_h | WEB, json={"vehicle_id": str(v.id), "hours": 24})
    assert r.status_code == 201, r.text
    reservation = r.json()
    assert reservation["status"] == "activa" and reservation["vehicle"]["status"] == "reservado"
    assert status_of(client, v.id) == "reservado"
    assert {"reservation.created", "vehicle.status_changed"} <= {e["type"] for e in published}

    # 2. Cliente crea la orden: la reserva se convierte
    r = client.post("/api/v1/orders", headers=client_h | WEB, json={"vehicle_id": str(v.id)})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "pendiente" and order["total_mxn"] == 450000.0
    assert order["reservation_id"] == reservation["id"]
    assert client.get(f"/api/v1/reservations/{reservation['id']}", headers=client_h).json()["status"] == "convertida"

    # 3. Pago simulado rechazado y luego aprobado
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=client_h,
                    json={"method": "tarjeta_simulada", "card_number": "4111 1111 1111 0000"})
    assert r.status_code == 201 and r.json()["status"] == "pendiente"
    assert r.json()["payments"][0]["status"] == "rechazado"
    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=client_h,
                    json={"method": "tarjeta_simulada", "card_number": "4111 1111 1111 1111"})
    assert r.json()["status"] == "pagada" and r.json()["payments"][-1]["reference"].startswith("SIM-")

    # 4. El cliente no puede confirmar la venta; el admin sí (desde AutoMarket.exe)
    assert client.post(f"/api/v1/orders/{order['id']}/confirm", headers=client_h).status_code == 403
    r = client.post(f"/api/v1/orders/{order['id']}/confirm", headers=admin_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmada" and r.json()["sale"]["sale_price_mxn"] == 450000.0

    # 5. La web ve el vehículo vendido y ya no se puede reservar
    assert status_of(client, v.id) == "vendido"
    r = client.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(v.id)})
    assert r.status_code == 409 and r.json()["code"] == "vehicle_not_available"
    assert db.scalar(select(Sale).where(Sale.vehicle_id == v.id)) is not None
    assert published[-1]["type"] == "vehicle.status_changed" and published[-1]["data"]["status"] == "vendido"

    # 6. Historial completo con el origen de cada operación
    hist = client.get("/api/v1/history", headers=admin_h, params={"vehicle_id": str(v.id)}).json()["items"]
    assert [(h["operation"], h["source"]) for h in reversed(hist)] == [
        ("reserva_creada", "web"), ("orden_creada", "web"), ("pago_rechazado", "web"),
        ("pago_aprobado", "web"), ("venta_confirmada", "desktop"),
    ]


def test_no_hay_reservas_dobles(client, customer, other_customer, make_vehicle):
    _, uno = customer
    _, dos = other_customer
    v = make_vehicle()
    assert client.post("/api/v1/reservations", headers=uno, json={"vehicle_id": str(v.id)}).status_code == 201
    r = client.post("/api/v1/reservations", headers=dos, json={"vehicle_id": str(v.id)})
    assert r.status_code == 409 and r.json()["code"] == "vehicle_not_available"
    r = client.post("/api/v1/orders", headers=dos, json={"vehicle_id": str(v.id)})
    assert r.status_code == 409 and r.json()["code"] == "vehicle_reserved_by_other"


def test_no_hay_ordenes_dobles(client, customer, other_customer, make_vehicle):
    _, uno = customer
    _, dos = other_customer
    v = make_vehicle()
    assert client.post("/api/v1/orders", headers=uno, json={"vehicle_id": str(v.id)}).status_code == 201
    r = client.post("/api/v1/orders", headers=dos, json={"vehicle_id": str(v.id)})
    assert r.status_code == 409 and r.json()["code"] == "vehicle_has_open_order"


def test_cancelar_reserva_libera_vehiculo(client, admin, customer, other_customer, make_vehicle, published):
    _, admin_h = admin
    _, client_h = customer
    _, otro_h = other_customer
    v = make_vehicle()
    res = client.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(v.id)}).json()

    assert client.post(f"/api/v1/reservations/{res['id']}/cancel", headers=otro_h).status_code == 404  # ajena
    r = client.post(f"/api/v1/reservations/{res['id']}/cancel", headers=client_h)
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
    assert status_of(client, v.id) == "disponible"
    assert published[-1]["data"]["status"] == "disponible"
    r = client.post(f"/api/v1/reservations/{res['id']}/cancel", headers=admin_h)
    assert r.status_code == 409 and r.json()["code"] == "reservation_not_active"


def test_admin_reserva_a_nombre_de_cliente_y_cliente_solo_ve_lo_suyo(client, admin, customer, other_customer,
                                                                   make_vehicle):
    _, admin_h = admin
    cliente, client_h = customer
    _, otro_h = other_customer
    v = make_vehicle()
    r = client.post("/api/v1/reservations", headers=admin_h,
                    json={"vehicle_id": str(v.id), "user_id": str(cliente.id)})
    assert r.status_code == 201 and r.json()["user"]["id"] == str(cliente.id)
    assert client.get("/api/v1/reservations", headers=client_h).json()["total"] == 1
    assert client.get("/api/v1/reservations", headers=otro_h).json()["total"] == 0
    r = client.post("/api/v1/reservations", headers=client_h,
                    json={"vehicle_id": str(make_vehicle().id), "user_id": str(admin[0].id)})
    assert r.status_code == 403


def test_reserva_vencida_libera_vehiculo(client, db, customer, make_vehicle, published):
    _, client_h = customer
    v = make_vehicle()
    res = client.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(v.id)}).json()
    pasado = datetime.now(timezone.utc) - timedelta(hours=3)
    db.execute(update(Reservation).where(Reservation.id == res["id"])
               .values(created_at=pasado - timedelta(hours=48), expires_at=pasado))

    assert expire_reservations(db) >= 1
    assert client.get(f"/api/v1/reservations/{res['id']}", headers=client_h).json()["status"] == "expirada"
    assert status_of(client, v.id) == "disponible"
    assert "reservation.expired" in {e["type"] for e in published}


def test_cancelar_orden_y_reglas_de_estado(client, admin, customer, make_vehicle):
    _, admin_h = admin
    _, client_h = customer
    v = make_vehicle()
    order = client.post("/api/v1/orders", headers=client_h, json={"vehicle_id": str(v.id)}).json()

    r = client.post(f"/api/v1/orders/{order['id']}/confirm", headers=admin_h)
    assert r.status_code == 409 and r.json()["code"] == "order_not_paid"

    client.post(f"/api/v1/orders/{order['id']}/payments", headers=client_h, json={"method": "efectivo_simulado"})
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=client_h)
    assert r.status_code == 403  # el cliente no cancela una orden ya pagada
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=admin_h)
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
    assert status_of(client, v.id) == "disponible"

    r = client.post(f"/api/v1/orders/{order['id']}/payments", headers=client_h, json={"method": "efectivo_simulado"})
    assert r.status_code == 409 and r.json()["code"] == "order_not_pending"
