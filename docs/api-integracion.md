# Guía de integración · API AutoMarket

Para el equipo que desarrolla la **página web de clientes**. La web y AutoMarket.exe usan la misma API
y la misma base de datos, así que todo cambio que haga uno lo ve el otro.

- **URL base (desarrollo):** `http://<IP-del-servidor>:8000/api/v1`
- **Documentación interactiva (Swagger):** `http://<IP-del-servidor>:8000/docs`
- **Especificación OpenAPI (para generar clientes):** `http://<IP-del-servidor>:8000/openapi.json`
- **Formato:** JSON (UTF-8). Fechas en ISO 8601 con zona horaria (UTC). Precios en MXN como número.

> La web **nunca** se conecta a PostgreSQL: todo pasa por esta API.

## 1. Autenticación

| Paso | Petición |
|---|---|
| Registrar cliente | `POST /auth/register` `{"email", "password" (8-72), "full_name", "phone"?}` → 201 |
| Iniciar sesión | `POST /auth/login` `{"email", "password"}` → `{"access_token", "expires_at", "user"}` |
| Usuario actual | `GET /auth/me` |

Envía el token en cada petición protegida:

```
Authorization: Bearer eyJhbGciOi...
X-Client-App: web
```

El token dura 8 horas. Cuando expira, la API responde `401` con `code: "invalid_token"` y hay que
volver a iniciar sesión. `X-Client-App: web` es opcional y sirve para que el historial registre que
la operación vino de la web.

## 2. Endpoints para la web

| Funcionalidad | Método y ruta | Sesión |
|---|---|---|
| Marcas y modelos (para los filtros) | `GET /brands` | No |
| Catálogo con búsqueda y filtros | `GET /vehicles` | No |
| Detalle de un vehículo | `GET /vehicles/{id}` | No |
| Reservar | `POST /reservations` `{"vehicle_id", "hours"?, "notes"?}` | Sí |
| Mis reservas | `GET /reservations?status=activa` | Sí |
| Cancelar reserva | `POST /reservations/{id}/cancel` | Sí |
| Solicitud de compra | `POST /orders` `{"vehicle_id"}` | Sí |
| Pago simulado | `POST /orders/{id}/payments` `{"method", "card_number"?}` | Sí |
| Mis pedidos | `GET /orders` y `GET /orders/{id}` | Sí |
| Cancelar pedido pendiente | `POST /orders/{id}/cancel` | Sí |

### Filtros de `GET /vehicles`

`q` (texto libre), `brand`, `model`, `body_type`, `status` (`disponible|reservado|vendido`),
`transmission` (`manual|automatica|cvt`), `fuel_type` (`gasolina|diesel|hibrido|electrico`),
`year_min`, `year_max`, `price_min`, `price_max`, `mileage_max`,
`sort` (`newest|price_asc|price_desc|year_desc|year_asc|mileage_asc`), `page`, `page_size` (máximo 100).

```
GET /api/v1/vehicles?brand=Mazda&body_type=SUV&price_max=600000&sort=price_asc&page=1&page_size=12
```

Respuesta paginada:

```json
{
  "items": [{
    "id": "4b1f…", "stock_number": "AM-31FC5AA5", "brand": "Mazda", "model": "CX-30",
    "body_type": "SUV", "year": 2026, "version": "i Grand Touring", "price_mxn": 525900.0,
    "mileage_km": 0, "color": "Gris Titanio", "transmission": "automatica", "fuel_type": "gasolina",
    "engine": "2.5L 186 hp", "description": "…", "status": "disponible",
    "primary_image": "https://www.mazda.mx/…png",
    "images": [{"id": 12, "url": "…", "is_primary": true, "position": 0}],
    "data_source": {"name": "Mazda México · catálogo oficial (scraping)", "kind": "real", "url": "…"},
    "row_version": 1, "created_at": "…", "updated_at": "…"
  }],
  "total": 14, "page": 1, "page_size": 12
}
```

**Imágenes:** si `url` empieza con `/media/...` es una foto subida desde AutoMarket.exe y hay que
anteponerle el servidor: `http://<IP-del-servidor>:8000/media/...`.

## 3. Estados y flujo de compra

```
Vehículo:  disponible ──reserva/orden──► reservado ──venta confirmada (admin)──► vendido
               ▲                              │
               └──── cancelación o vencimiento ┘

Reserva:   activa ─► cancelada | expirada (automático al vencer) | convertida (pasó a orden)
Orden:     pendiente ──pago aprobado──► pagada ──admin confirma en AutoMarket.exe──► confirmada
               └────────────────────────┴──► cancelada
```

Compra simulada desde la web:

1. `POST /orders` con el `vehicle_id`. Si el cliente tenía una reserva activa de ese vehículo, se convierte en la orden.
2. `POST /orders/{id}/payments` con `{"method": "tarjeta_simulada", "card_number": "4111 1111 1111 1111"}`.
   - No se mueve dinero real y el número de tarjeta **no se guarda**.
   - Para probar un rechazo: una tarjeta que termine en `0000` o `"simulate_decline": true`.
   - Métodos: `tarjeta_simulada`, `transferencia_simulada`, `efectivo_simulado`.
3. La orden queda `pagada`. Un administrador confirma la venta desde AutoMarket.exe y el vehículo pasa a `vendido`.
4. La web consulta `GET /orders/{id}`; cuando `status = "confirmada"`, el campo `sale` trae los datos de la venta.

## 4. Errores

Todos los errores tienen el mismo formato. **Programen contra `code`**, que no cambia; `detail` es un mensaje legible:

```json
{"detail": "El vehículo no está disponible (estado: reservado)", "code": "vehicle_not_available"}
```

| HTTP | `code` | Cuándo |
|---|---|---|
| 401 | `not_authenticated`, `invalid_token`, `invalid_credentials` | Falta el token, el token es inválido o la contraseña es incorrecta |
| 403 | `admin_required`, `forbidden` | El cliente intenta una operación de administrador o ajena |
| 404 | `vehicle_not_found`, `reservation_not_found`, `order_not_found` | No existe o no es suyo |
| 409 | `vehicle_not_available` | Alguien más ya reservó o compró el vehículo |
| 409 | `vehicle_reserved_by_other`, `vehicle_has_open_order`, `vehicle_sold` | Conflictos de estado del vehículo |
| 409 | `reservation_not_active`, `order_not_pending`, `order_not_open` | Conflictos de estado de reservas y órdenes |
| 409 | `email_taken` | El correo ya está registrado |
| 422 | (sin `code`; `detail` es una lista) | Validación de datos: `detail[i].loc` indica el campo |

Un `409` es normal cuando dos personas compiten por el mismo auto: muestren un mensaje
("Este vehículo acaba de ser reservado") y recarguen el detalle.

## 5. Garantías del backend

- **Sin reservas ni ventas duplicadas:** cada operación bloquea la fila del vehículo dentro de una
  transacción, y la base de datos tiene índices únicos como segunda barrera. Se probó con 10 clientes
  simultáneos: exactamente 1 obtiene la reserva.
- **Vencimiento automático:** el servidor revisa cada minuto las reservas vencidas y libera los vehículos.
- **Precio congelado:** la orden guarda el precio del momento en que se creó.
- **Auditoría:** cada cambio queda registrado con el usuario y el origen (`web` o `desktop`).
- **CORS:** solo se aceptan los orígenes configurados. Avísennos el dominio y puerto de su
  página (por ejemplo `http://localhost:3000`) para agregarlo.

## 6. Tiempo real (WebSocket)

Con el WebSocket, la página web se actualiza sola cuando AutoMarket.exe cambia un precio, registra un
vehículo o confirma una venta, y también cuando otro cliente reserva.

```
ws://<IP-del-servidor>:8000/api/v1/ws?client=web                  # visitante sin sesión
ws://<IP-del-servidor>:8000/api/v1/ws?client=web&token=<JWT>      # cliente con sesión
```

Ejemplo en JavaScript:

```js
let lastSeq = null;

function conectar(token) {
  const url = `ws://${SERVIDOR}:8000/api/v1/ws?client=web` + (token ? `&token=${token}` : "");
  const ws = new WebSocket(url);

  ws.onmessage = (msg) => {
    const ev = JSON.parse(msg.data);
    if (ev.type === "connection.ready" || ev.type === "pong") return;
    if (lastSeq !== null && ev.seq !== lastSeq + 1) recargarCatalogo(); // se perdieron eventos
    lastSeq = ev.seq;

    switch (ev.type) {
      case "vehicle.status_changed": actualizarEstado(ev.data.id, ev.data.status); break;
      case "vehicle.updated":        actualizarVehiculo(ev.data); break;   // vehículo completo
      case "vehicle.created":        agregarVehiculo(ev.data); break;
      case "vehicle.deleted":        quitarVehiculo(ev.data.id); break;
      case "order.paid":             /* el pedido del cliente se pagó */ break;
      case "sale.confirmed":         /* AutoMarket.exe confirmó la compra del cliente */ break;
    }
  };
  const ping = setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
  ws.onclose = (e) => {
    clearInterval(ping);
    if (e.code === 4401) return pedirLoginDeNuevo();
    setTimeout(() => { recargarCatalogo(); conectar(token); }, 3000);   // reconexión automática
  };
}
```

### Formato de los mensajes

```json
{"seq": 57, "type": "vehicle.status_changed", "occurred_at": "2026-10-19T21:58:03.120+00:00",
 "data": {"id": "4b1f…", "stock_number": "AM-0ADF6868", "status": "reservado", "row_version": 3,
          "reason": "reserva_creada"}}
```

| Evento | Quién lo recibe | `data` |
|---|---|---|
| `vehicle.created` | Todos | Vehículo completo (mismo formato que `GET /vehicles/{id}`) |
| `vehicle.updated` | Todos | Vehículo completo + `changed` (lista de campos modificados) |
| `vehicle.deleted` | Todos | `id`, `stock_number` |
| `vehicle.status_changed` | Todos | `id`, `stock_number`, `status`, `row_version`, `reason` |
| `reservation.created` / `.cancelled` / `.expired` | Admin y el cliente dueño | `id`, `vehicle_id`, `user_id`, … |
| `order.created` / `.paid` / `.payment_declined` / `.cancelled` | Admin y el cliente dueño | `id`, `vehicle_id`, `user_id`, `status`, … |
| `sale.confirmed` | Admin y el cliente comprador | `id`, `order_id`, `vehicle_id`, `user_id`, `sale_price_mxn` |

### Reglas

- Los eventos se envían **después** de que el cambio se guardó en la base de datos. Si llega un
  evento, el dato ya se puede consultar por REST.
- `seq` aumenta de uno en uno. Si detectan un salto, o tras reconectarse, recarguen los datos por REST.
- El WebSocket solo **notifica**: las operaciones (reservar, pagar…) se hacen siempre por REST.
- Códigos de cierre: `4401` token inválido, `4403` origen no permitido (pidan que agreguemos su
  dominio a `CORS_ORIGINS`) y `1013` cliente demasiado lento.
- Envíen `"ping"` cada 25-30 s para mantener viva la conexión; el servidor responde `{"type": "pong"}`.

### Prueba de comunicación bidireccional

`scripts/demo_sincronizacion.py` simula AutoMarket.exe y la web al mismo tiempo y verifica que cada
operación de un lado llegue al otro. Guarda la evidencia en `docs/evidencias/`.
