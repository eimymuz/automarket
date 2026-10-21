"""Sincronización bidireccional por WebSocket: AutoMarket.exe (admin) <-> página web (clientes/visitantes)."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.v1.ws import get_user_lookup
from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models import User
from tests.conftest import requires_db

pytestmark = requires_db
WS = "/api/v1/ws"


@pytest.fixture
def live(db, tmp_path, monkeypatch):
    """TestClient con lifespan activo (arranca el difusor de eventos) y la BD transaccional de la prueba."""
    monkeypatch.setattr(get_settings(), "media_dir", tmp_path)

    def lookup(user_id):
        user = db.get(User, user_id)
        return (str(user.id), user.role.name) if user and user.is_active else None

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_user_lookup] = lambda: lookup
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def token_of(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def receive_until(ws, event_type: str, limit: int = 20) -> list[dict]:
    """Lee mensajes hasta encontrar `event_type`; devuelve todos los recibidos (incluido ese)."""
    received = []
    for _ in range(limit):
        msg = ws.receive_json()
        received.append(msg)
        if msg["type"] == event_type:
            return received
    raise AssertionError(f"No llegó {event_type}; recibidos: {[m['type'] for m in received]}")


def test_desktop_cambia_precio_y_la_web_lo_recibe(live, admin, make_vehicle):
    """AutoMarket.exe -> web: un visitante sin sesión ve el nuevo precio al instante."""
    _, admin_h = admin
    v = make_vehicle()
    with live.websocket_connect(f"{WS}?client=web") as web:
        assert web.receive_json()["data"]["role"] == "anonimo"
        r = live.patch(f"/api/v1/vehicles/{v.id}", headers=admin_h,
                       json={"row_version": v.row_version, "price_mxn": "399900"})
        assert r.status_code == 200
        event = receive_until(web, "vehicle.updated")[-1]
        assert event["data"]["id"] == str(v.id) and event["data"]["price_mxn"] == 399900.0
        assert event["data"]["changed"] == ["price_mxn"] and event["seq"] >= 1


def test_web_reserva_y_desktop_lo_recibe(live, admin, customer, make_vehicle):
    """Web -> AutoMarket.exe: el administrador ve la reserva y el cambio de estado."""
    _, admin_h = admin
    cliente, client_h = customer
    v = make_vehicle()
    with live.websocket_connect(f"{WS}?token={token_of(admin_h)}&client=desktop") as desktop:
        assert desktop.receive_json()["data"]["role"] == "admin"
        r = live.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(v.id)})
        assert r.status_code == 201

        msgs = receive_until(desktop, "vehicle.status_changed")
        reserva = next(m for m in msgs if m["type"] == "reservation.created")
        assert reserva["data"]["vehicle_id"] == str(v.id) and reserva["data"]["user_id"] == str(cliente.id)
        assert msgs[-1]["data"] == msgs[-1]["data"] | {"id": str(v.id), "status": "reservado"}


def test_compra_simulada_web_y_confirmacion_desktop(live, admin, customer, make_vehicle):
    """Flujo completo con los dos lados escuchando."""
    _, admin_h = admin
    _, client_h = customer
    v = make_vehicle()
    with live.websocket_connect(f"{WS}?token={token_of(admin_h)}") as desktop, \
         live.websocket_connect(f"{WS}?token={token_of(client_h)}") as web:
        desktop.receive_json(), web.receive_json()

        order = live.post("/api/v1/orders", headers=client_h, json={"vehicle_id": str(v.id)}).json()
        live.post(f"/api/v1/orders/{order['id']}/payments", headers=client_h, json={"method": "transferencia_simulada"})
        pagada = receive_until(desktop, "order.paid")[-1]
        assert pagada["data"]["id"] == order["id"] and pagada["data"]["status"] == "pagada"

        live.post(f"/api/v1/orders/{order['id']}/confirm", headers=admin_h)
        msgs = receive_until(web, "sale.confirmed")
        assert msgs[-1]["data"]["sale_price_mxn"] == 450000.0
        vendido = receive_until(web, "vehicle.status_changed")[-1]
        assert vendido["data"]["status"] == "vendido"

        seqs = [m["seq"] for m in msgs + [vendido] if "seq" in m]
        assert seqs == sorted(seqs)


def test_eventos_privados_solo_para_su_dueno(live, customer, other_customer, make_vehicle):
    _, client_h = customer
    _, other_h = other_customer
    v = make_vehicle()
    marker = make_vehicle()
    with live.websocket_connect(f"{WS}?token={token_of(other_h)}") as otro, \
         live.websocket_connect(f"{WS}?token={token_of(client_h)}") as dueno:
        otro.receive_json(), dueno.receive_json()
        live.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(v.id)})
        # Reserva de "marcador": cuando el otro cliente la vea, ya debió recibir todo lo anterior
        live.post("/api/v1/reservations", headers=other_h, json={"vehicle_id": str(marker.id)})

        otro_msgs = receive_until(otro, "reservation.created")
        ajenas = [m for m in otro_msgs if m["type"] == "reservation.created" and m["data"]["vehicle_id"] == str(v.id)]
        assert not ajenas, "un cliente recibió la reserva de otro"
        assert any(m["type"] == "vehicle.status_changed" and m["data"]["id"] == str(v.id) for m in otro_msgs)

        propias = receive_until(dueno, "reservation.created")
        assert propias[-1]["data"]["vehicle_id"] == str(v.id)


def test_ping_pong(live):
    with live.websocket_connect(WS) as ws:
        ws.receive_json()
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


def test_token_invalido_cierra_con_4401(live):
    with pytest.raises(WebSocketDisconnect) as exc:
        with live.websocket_connect(f"{WS}?token=no.es.valido") as ws:
            ws.receive_json()
    assert exc.value.code == 4401


def test_origen_no_permitido_cierra_con_4403(live):
    with pytest.raises(WebSocketDisconnect) as exc:
        with live.websocket_connect(WS, headers={"origin": "https://sitio-malicioso.com"}) as ws:
            ws.receive_json()
    assert exc.value.code == 4403
