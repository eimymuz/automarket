from tests.conftest import requires_db

pytestmark = requires_db


def test_dashboard_refleja_reservas_y_ventas(client, admin, customer, make_vehicle):
    _, admin_h = admin
    _, client_h = customer
    antes = client.get("/api/v1/stats/dashboard", headers=admin_h).json()

    reservado, vendido = make_vehicle(), make_vehicle(price_mxn=700000)
    client.post("/api/v1/reservations", headers=client_h, json={"vehicle_id": str(reservado.id)})
    order = client.post("/api/v1/orders", headers=client_h, json={"vehicle_id": str(vendido.id)}).json()
    client.post(f"/api/v1/orders/{order['id']}/payments", headers=client_h, json={"method": "efectivo_simulado"})
    client.post(f"/api/v1/orders/{order['id']}/confirm", headers=admin_h)

    r = client.get("/api/v1/stats/dashboard", headers=admin_h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["vehicles"]["total"] == antes["vehicles"]["total"] + 2
    assert d["vehicles"]["by_status"]["reservado"] == antes["vehicles"]["by_status"]["reservado"] + 1
    assert d["vehicles"]["by_status"]["vendido"] == antes["vehicles"]["by_status"]["vendido"] + 1
    assert d["reservations_active"] == antes["reservations_active"] + 1
    assert d["sales"]["total"] == antes["sales"]["total"] + 1
    assert d["sales"]["revenue_last_30_days_mxn"] == antes["sales"]["revenue_last_30_days_mxn"] + 700000
    assert d["recent_activity"][0]["operation"] == "venta_confirmada"
    assert sum(b["total"] for b in d["price_ranges"]) == d["vehicles"]["total"]
    assert any(b["brand"] == "MarcaPrueba" for b in d["by_brand"])


def test_dashboard_solo_admin(client, customer):
    _, client_h = customer
    assert client.get("/api/v1/stats/dashboard", headers=client_h).status_code == 403
