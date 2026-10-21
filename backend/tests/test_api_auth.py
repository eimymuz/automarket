from tests.conftest import PASSWORD, requires_db

pytestmark = requires_db


def test_registro_login_y_me(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "Nuevo.Cliente@Test.mx", "password": "ClaveSegura1", "full_name": "Nuevo Cliente",
    })
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "cliente" and r.json()["email"] == "nuevo.cliente@test.mx"
    assert "password_hash" not in r.json()

    r = client.post("/api/v1/auth/login", json={"email": "nuevo.cliente@test.mx", "password": "ClaveSegura1"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["full_name"] == "Nuevo Cliente"


def test_registro_duplicado(client, customer):
    user, _ = customer
    r = client.post("/api/v1/auth/register", json={"email": user.email.upper(), "password": "ClaveSegura1",
                                                   "full_name": "Otro"})
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


def test_validaciones_de_registro(client):
    r = client.post("/api/v1/auth/register", json={"email": "no-es-correo", "password": "123", "full_name": "A"})
    assert r.status_code == 422
    campos = {e["loc"][-1] for e in r.json()["detail"]}
    assert {"email", "password", "full_name"} <= campos


def test_login_incorrecto(client, customer):
    user, _ = customer
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": "incorrecta"})
    assert r.status_code == 401 and r.json()["code"] == "invalid_credentials"
    r = client.post("/api/v1/auth/login", json={"email": "noexiste@test.mx", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["code"] == "invalid_credentials"


def test_token_requerido_e_invalido(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token.falso.123"})
    assert r.status_code == 401 and r.json()["code"] == "invalid_token"


def test_cliente_no_puede_usar_endpoints_de_admin(client, customer):
    _, headers = customer
    r = client.post("/api/v1/vehicles", headers=headers, json={})
    assert r.status_code == 403 and r.json()["code"] == "admin_required"
    assert client.get("/api/v1/history", headers=headers).status_code == 403
    assert client.get("/api/v1/sales", headers=headers).status_code == 403
