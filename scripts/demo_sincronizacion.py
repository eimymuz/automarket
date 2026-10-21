"""Demostración de comunicación bidireccional AutoMarket.exe <-> página web, contra el servidor real.

Simula dos aplicaciones independientes, cada una con su propio WebSocket:
  - DESKTOP: un administrador (como AutoMarket.exe)
  - WEB:     un cliente de la página web

Cada paso hace una operación REST en un lado y verifica que el OTRO lado reciba el evento.

Uso (con el backend corriendo):
    ..\\backend\\.venv\\Scripts\\python.exe demo_sincronizacion.py --admin-email admin@automarket.mx
    ... --venta    # además vende un vehículo de demostración creado para la prueba

Sin --venta el inventario queda como estaba (el precio se restaura y la reserva/orden se cancelan).
Las contraseñas se piden de forma oculta (o variables de entorno AUTOMARKET_ADMIN_PASSWORD y
AUTOMARKET_DEMO_PASSWORD). El cliente de demostración se registra si no existe.
"""
import argparse
import getpass
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from websockets.sync.client import connect

DEMO_EMAIL = "cliente.demo@automarket.mx"
EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "docs" / "evidencias"
TIMEOUT = 5.0


class App:
    """Una aplicación cliente: sesión REST + WebSocket escuchando en segundo plano."""

    def __init__(self, name: str, api: str, token: str, client_app: str):
        self.name, self.api = name, api
        self.http = httpx.Client(base_url=f"{api}/api/v1", timeout=15,
                                 headers={"Authorization": f"Bearer {token}", "X-Client-App": client_app})
        ws_url = api.replace("http", "ws", 1) + f"/api/v1/ws?token={token}&client={client_app}"
        self._ws_ctx = connect(ws_url)
        self.ws = self._ws_ctx.__enter__()
        self.events: list[dict] = []
        self.cond = threading.Condition()
        ready = json.loads(self.ws.recv(timeout=TIMEOUT))
        print(f"  [{name}] WebSocket conectado como '{ready['data']['role']}'")
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        try:
            for raw in self.ws:
                event = json.loads(raw)
                event["_received_at"] = datetime.now(timezone.utc)
                with self.cond:
                    self.events.append(event)
                    self.cond.notify_all()
        except Exception:
            pass

    def wait_for(self, event_type: str, since: int, **match) -> dict | None:
        """Espera un evento de ese tipo cuyos datos contengan `match`, llegado después del índice `since`."""
        deadline = time.monotonic() + TIMEOUT
        with self.cond:
            while True:
                for e in self.events[since:]:
                    if e["type"] == event_type and all(e["data"].get(k) == v for k, v in match.items()):
                        return e
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.cond.wait(remaining)

    def mark(self) -> int:
        with self.cond:
            return len(self.events)

    def call(self, method: str, path: str, **kw) -> dict:
        r = self.http.request(method, path, **kw)
        if r.status_code >= 400:
            sys.exit(f"  [{self.name}] {method} {path} -> {r.status_code}: {r.text}")
        return r.json() if r.content else {}

    def close(self):
        self._ws_ctx.__exit__(None, None, None)
        self.http.close()


def latency_ms(event: dict) -> float:
    sent = datetime.fromisoformat(event["occurred_at"])
    return (event["_received_at"] - sent).total_seconds() * 1000


def login(api: str, email: str, password: str) -> str:
    r = httpx.post(f"{api}/api/v1/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        raise PermissionError(r.json().get("detail", r.text))
    return r.json()["access_token"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--venta", action="store_true", help="Incluir venta completa de un vehículo de demostración")
    args = parser.parse_args()

    password = os.environ.get("AUTOMARKET_ADMIN_PASSWORD") or getpass.getpass("Contraseña del admin: ")
    # La contraseña del cliente de demostración nunca se escribe en el código
    demo_password = (os.environ.get("AUTOMARKET_DEMO_PASSWORD")
                     or getpass.getpass(f"Contraseña del cliente {DEMO_EMAIL} (se crea si no existe): "))
    demo_client = {"email": DEMO_EMAIL, "password": demo_password, "full_name": "Cliente Demo Web"}
    print("\n== Conectando las dos aplicaciones")
    try:
        admin_token = login(args.api, args.admin_email, password)
    except PermissionError as exc:
        sys.exit(f"No se pudo iniciar sesión como admin: {exc}")
    try:
        client_token = login(args.api, DEMO_EMAIL, demo_password)
    except PermissionError:
        r = httpx.post(f"{args.api}/api/v1/auth/register", json=demo_client, timeout=15)
        if r.status_code == 409:
            sys.exit(f"{DEMO_EMAIL} ya existe con otra contraseña o está desactivado; "
                     "reactívalo con una contraseña nueva o usa otra.")
        r.raise_for_status()
        client_token = login(args.api, DEMO_EMAIL, demo_password)
        print(f"  Se registró el cliente de demostración {DEMO_EMAIL}")

    desktop = App("DESKTOP", args.api, admin_token, "desktop")
    web = App("WEB", args.api, client_token, "web")
    results: list[dict] = []

    def check(step: str, receiver: App, event_type: str, since: int, **match) -> None:
        event = receiver.wait_for(event_type, since, **match)
        ok = event is not None
        lat = latency_ms(event) if ok else None
        results.append({"paso": step, "receptor": receiver.name, "evento": event_type, "ok": ok,
                        "latencia_ms": round(lat, 1) if ok else None})
        mark = "OK " if ok else "FALLA"
        print(f"    [{mark}] {receiver.name} recibió {event_type}" + (f" en {lat:.0f} ms" if ok else " (timeout)"))

    try:
        # Vehículo para la demo
        if args.venta:
            v = desktop.call("POST", "/vehicles", json={
                "brand": "Demo", "model": "Vehículo de demostración", "body_type": "Sedán", "year": 2024,
                "version": "Sincronización", "price_mxn": "250000", "mileage_km": 1000, "color": "Blanco",
                "transmission": "automatica", "fuel_type": "gasolina", "engine": "1.5L",
                "description": "Creado por scripts/demo_sincronizacion.py para demostrar la venta.",
            })
        else:
            page = web.call("GET", "/vehicles", params={"status": "disponible", "sort": "price_asc", "page_size": 1})
            v = page["items"][0]
        vid, original_price = v["id"], v["price_mxn"]
        print(f"\n== Vehículo: {v['stock_number']} {v['brand']} {v['model']} {v['version']} {v['year']} "
              f"(${original_price:,.0f})")

        print("\n1) DESKTOP cambia el precio  ->  la WEB debe verlo")
        m = web.mark()
        new_price = original_price - 10_000
        v = desktop.call("PATCH", f"/vehicles/{vid}", json={"row_version": v["row_version"], "price_mxn": str(new_price)})
        check("precio desde desktop", web, "vehicle.updated", m, id=vid, price_mxn=float(new_price))

        print("\n2) WEB reserva el vehículo  ->  DESKTOP debe verlo reservado")
        m = desktop.mark()
        reservation = web.call("POST", "/reservations", json={"vehicle_id": vid, "hours": 1, "notes": "Demo"})
        check("reserva desde web", desktop, "reservation.created", m, id=reservation["id"])
        check("reserva desde web", desktop, "vehicle.status_changed", m, id=vid, status="reservado")

        print("\n3) WEB crea la orden y paga (simulado)  ->  DESKTOP debe ver la orden pagada")
        m = desktop.mark()
        order = web.call("POST", "/orders", json={"vehicle_id": vid})
        check("orden desde web", desktop, "order.created", m, id=order["id"])
        web.call("POST", f"/orders/{order['id']}/payments", json={"method": "tarjeta_simulada",
                                                                   "card_number": "4111 1111 1111 1111"})
        check("pago desde web", desktop, "order.paid", m, id=order["id"])

        if args.venta:
            print("\n4) DESKTOP confirma la venta  ->  la WEB debe ver el vehículo vendido")
            m = web.mark()
            desktop.call("POST", f"/orders/{order['id']}/confirm")
            check("venta desde desktop", web, "sale.confirmed", m, order_id=order["id"])
            check("venta desde desktop", web, "vehicle.status_changed", m, id=vid, status="vendido")
        else:
            print("\n4) DESKTOP cancela la orden  ->  la WEB debe ver el vehículo disponible")
            m = web.mark()
            desktop.call("POST", f"/orders/{order['id']}/cancel")
            check("cancelación desde desktop", web, "order.cancelled", m, id=order["id"])
            check("cancelación desde desktop", web, "vehicle.status_changed", m, id=vid, status="disponible")

            print("\n5) DESKTOP restaura el precio original  ->  la WEB debe verlo")
            m = web.mark()
            current = web.call("GET", f"/vehicles/{vid}")
            desktop.call("PATCH", f"/vehicles/{vid}", json={"row_version": current["row_version"],
                                                            "price_mxn": str(original_price)})
            check("restaurar precio", web, "vehicle.updated", m, id=vid, price_mxn=float(original_price))
    finally:
        desktop.close()
        web.close()

    passed = sum(r["ok"] for r in results)
    lat = [r["latencia_ms"] for r in results if r["ok"]]
    print(f"\n== Resultado: {passed}/{len(results)} verificaciones correctas"
          + (f" · latencia promedio {sum(lat) / len(lat):.0f} ms, máxima {max(lat):.0f} ms" if lat else ""))

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE_DIR / f"sincronizacion_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"api": args.api, "venta": args.venta, "vehiculo": vid, "resultados": results,
                               "fecha": datetime.now(timezone.utc).isoformat()}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"   Evidencia guardada en {out}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
