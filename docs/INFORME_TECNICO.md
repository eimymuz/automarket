# AutoMarket · Informe técnico

Proyecto de la materia **Ingeniería de Datos**. AutoMarket es un sistema de administración de una agencia
de compraventa de automóviles. Tiene tres partes que comparten un mismo backend:

- **AutoMarket.exe**: aplicación de escritorio para los administradores.
- **Página web externa**: la desarrolla otro equipo para los clientes.
- **Pipeline de datos**: llena la base de datos con vehículos obtenidos por scraping.

## 1. Arquitectura

```
 AutoMarket.exe (Electron + React + TS) ──┐  REST (JSON + JWT)        ┌─► PostgreSQL 18
                                          ├─────────────────► FastAPI ─┤   (13 tablas, triggers
 Página web (otro equipo) ────────────────┘  ◄── WebSocket ── eventos  │    de auditoría)
                                                                       │
 Pipeline de datos (Python + Pandas) ── scraping → limpieza → carga ───┘
```

| Capa | Tecnología | Carpeta |
|---|---|---|
| Escritorio | Electron 44, React 19, TypeScript, Vite 8 (electron-vite), React Query, Recharts | `desktop/` |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.1, Alembic, Pydantic 2, JWT + bcrypt, WebSockets | `backend/` |
| Base de datos | PostgreSQL 18 | migraciones en `backend/alembic/` |
| Ingeniería de datos | httpx, Pandas, NumPy | `data-pipeline/` |
| Instalador y despliegue | electron-builder (NSIS), tarea programada de Windows, Docker Compose | `desktop/`, `scripts/` |

**Principios de diseño:**
1. **Una sola fuente de verdad.** Ningún cliente guarda inventario propio, y PostgreSQL no se expone a los clientes.
2. **Las reglas críticas viven en la base de datos.** Índices únicos parciales, restricciones CHECK y
   triggers de auditoría siguen protegiendo los datos aunque falle el código de la aplicación.
3. **Los eventos se publican después del commit.** Lo que un cliente recibe por WebSocket ya se puede
   consultar por REST.

## 2. Cumplimiento de requisitos

### 2.1 Funcionalidades de AutoMarket.exe

| # | Requisito | Implementación | Evidencia |
|---|---|---|---|
| 1 | Dashboard general | `DashboardPage.tsx` con 6 indicadores, 3 gráficas con vista de tabla, tabla por marca y actividad reciente. Endpoint `/stats/dashboard`. | `test_api_stats.py` |
| 2 | Catálogo de 100 o más vehículos | **121 vehículos** de 18 modelos (Honda y Mazda) | `data-pipeline/evidence/*/estadisticas.md` |
| 3 | Registro de automóviles | `NewVehiclePage.tsx` + `POST /vehicles` (crea la marca y el modelo si no existen) | `test_admin_registra_vehiculo…` |
| 4 | Edición y eliminación controlada | `PATCH` con bloqueo optimista (`row_version`); baja lógica (`deleted_at`) solo de vehículos disponibles | `test_edicion_simultanea_detectada`, `test_baja_controlada` |
| 5 | Administración de fotografías | Subir (JPG, PNG o WEBP de hasta 5 MB, con validación de la firma binaria), elegir la principal y borrar | `test_fotografias`, `test_archivo_que_no_es_imagen` |
| 6 | Búsqueda y filtros | Texto libre y 11 filtros, 6 órdenes y paginación | `test_catalogo_publico_con_filtros` |
| 7 | Control de disponibilidad | Estados `disponible` / `reservado` / `vendido`, que solo cambian mediante operaciones de negocio | `test_flujo_completo…` |
| 8 | Gestión de reservas | Pantalla de reservas: vigencia, tiempo restante, cancelación y vencimiento automático cada 60 s | `test_reserva_vencida_libera_vehiculo` |
| 9 | Compras simuladas | Pantalla de órdenes con los pagos simulados (aprobado o rechazado) | `test_cancelar_orden_y_reglas_de_estado` |
| 10 | Confirmación de ventas | `POST /orders/{id}/confirm`, solo para admin y solo sobre órdenes pagadas | `test_flujo_completo…` |
| 11 | Historial de operaciones | `operation_history` con origen (`desktop`, `web`, `sistema`, `pipeline`) y autor | Pantalla Historial |
| 12 | Estadísticas y gráficas | Dashboard en vivo y estadísticas del pipeline | `estadisticas.md` |
| 13 | Autenticación de administradores | JWT de 8 h; AutoMarket.exe rechaza cuentas que no sean de administrador | `test_api_auth.py` |
| 14 | Sincronización con la web | WebSocket con reconexión automática y avisos nativos | `test_realtime.py`, demostración |

### 2.2 API para la página web

Consulta y filtros, registro e inicio de sesión de clientes, reservas, cancelaciones, solicitudes de
compra, pagos simulados, consulta de pedidos y estado de cada vehículo: **todo está implementado**
(21 endpoints REST y 1 WebSocket). La guía de integración para el otro equipo está en `docs/api-integracion.md`
y la referencia interactiva en Swagger (`/docs`).

### 2.3 Base de datos

Tablas: `vehicles`, `vehicle_images`, `brands`, `vehicle_models`, `data_sources`, `users`, `roles`,
`reservations`, `purchase_orders`, `payments`, `sales`, `operation_history` y `audit_log`. Están
normalizadas: la marca y el modelo viven en sus propias tablas y la procedencia en `data_sources`.
El vehículo guarda todos los campos solicitados, más el folio, la carrocería, la versión de fila y la
fecha de baja. El diagrama entidad-relación está en `docs/modelo-datos.md`.

### 2.4 Ingeniería de datos

| # | Requisito | Cómo se cumplió |
|---|---|---|
| 1-2 | 100 o más registros con referencia a catálogos automotrices | Scraping de **honda.mx** y **mazda.mx**: 28 páginas → 44 registros crudos → 48 versiones limpias → 121 unidades |
| 3 | Distinguir datos reales de datos de prueba | `data_sources.kind`: `real` (48, catálogo oficial), `referencia` (73, seminuevos derivados) y `prueba` |
| 4-8 | Limpieza, duplicados, nulos, tipos y normalización | `transform.py` con Pandas: llave natural para duplicados, reporte de nulos antes y después, validación de año, precio, transmisión y motor, formato título conservando siglas, enums y precios numéricos |
| 9 | Procedencia y fecha | `data_sources` (URL y `collected_at`), `manifest_descargas.json` (SHA-256 por URL) |
| 10 | Carga en PostgreSQL | `load.py`: una sola transacción, idempotente (`ON CONFLICT`), folio estable por hash |
| 11 | Estadísticas | `stats.py` → `estadisticas.md` |
| 12 | Evidencias | `raw/<corrida>/` con el HTML original y `evidence/<corrida>/` con log, manifiesto, reportes, rechazados y duplicados |
| — | Fuentes permitidas, sin APIs externas | `robots.txt` revisado antes de cada URL. Se descartaron Toyota, Chevrolet y VW. User-Agent propio, 2 s entre peticiones. El sistema no depende de los sitios en ejecución. |

### 2.5 Reservas y compras simuladas

Sin dinero real: los pagos son simulados y el número de tarjeta no se guarda. Para evitar duplicados
hay tres barreras:

1. `SELECT … FOR UPDATE` sobre el vehículo.
2. Validación del estado dentro de la misma transacción.
3. Índices únicos parciales: una reserva activa y una orden abierta por vehículo, y una venta por vehículo.

**Prueba de concurrencia real:** 10 conexiones independientes intentaron reservar el mismo auto al mismo
tiempo. Exactamente **1** lo consiguió y las otras 9 recibieron `409` (`test_concurrency.py`). Todas las
operaciones adquieren los bloqueos en el mismo orden (primero el vehículo, después la reserva) para
evitar deadlocks.

### 2.6 Comunicación y seguridad

- **API documentada:** REST con OpenAPI/Swagger; los errores siempre tienen el formato `{detail, code}`.
- **Tiempo real:** WebSocket con eventos públicos (`vehicle.*`) y privados (reservas, órdenes y ventas,
  solo para admin y el cliente dueño). Incluye número de secuencia para detectar eventos perdidos.
- **Autenticación y autorización:** JWT, roles `admin` y `cliente`, y validación de entradas con Pydantic.
- **Orígenes permitidos:** CORS restringido; el WebSocket valida el origen (4403) y el token (4401).
- **Auditoría:** trigger que guarda la fila antes y después de cada cambio, con el usuario
  (`SET LOCAL app.user_id`) y sin contraseñas.
- **Despliegue escalonado:** local → LAN → internet (`docs/despliegue.md`).

### 2.7 Instalador de Windows

`desktop/release/AutoMarket-Setup-1.0.0.exe` (NSIS, x64, 107 MB). No requiere Node.js ni Python y la URL
del servidor se configura desde la app. El backend corre aparte, como tarea de Windows o en Docker, y
está disponible aunque AutoMarket.exe esté cerrado.

## 3. Pruebas

| Suite | Pruebas | Cubre |
|---|---|---|
| `backend/tests` | **44** | esquema y restricciones, auth, vehículos, fotos, flujo de compra, privacidad, vencimiento, concurrencia real, WebSockets, estadísticas |
| `data-pipeline/tests` | **22** | limpieza de precios, modelos, versiones, transmisiones, combustibles, motor, carrocería, folios y depreciación |
| `scripts/demo_sincronizacion.py` | 8 verificaciones | comunicación bidireccional contra el servidor real (latencia de 0 a 3 ms) |
| Revisión visual | capturas a 1366 y 1024 px | todas las pantallas y la actualización en vivo del dashboard |

Las pruebas del backend usan PostgreSQL real dentro de una transacción que se revierte, así que no dejan
datos. La prueba de concurrencia limpia lo que crea.

```powershell
cd backend;        .\.venv\Scripts\python.exe -m pytest -q
cd data-pipeline;  ..\backend\.venv\Scripts\python.exe -m pytest tests -q
cd scripts;        ..\backend\.venv\Scripts\python.exe demo_sincronizacion.py --admin-email <admin>
```

## 4. Limitaciones conocidas

| Limitación | Impacto | Cómo se resolvería |
|---|---|---|
| Los seminuevos son **derivados** del catálogo (año, km y precio calculados), no anuncios reales | Están etiquetados como `referencia` en `data_sources` | Fuente de seminuevos que permita su uso |
| Las fotos del catálogo se enlazan desde los sitios de las marcas | Si cambian sus URL, se pierde la imagen | Subir fotos propias desde AutoMarket.exe (ya soportado) |
| Un solo worker de uvicorn | Suficiente para el proyecto | PostgreSQL LISTEN/NOTIFY o Redis para varios workers |
| Instalador sin firma digital | Advertencia de SmartScreen | Certificado de firma de código |
| Configuración Docker sin ejecutar (Docker Desktop apagado) | Solo se validó la sintaxis | Probar con `docker compose up` |
| PostgreSQL nativo escucha en todas las interfaces | `pg_hba.conf` solo permite conexiones locales | `listen_addresses = 'localhost'` (`docs/despliegue.md`) |
| El token JWT no se puede revocar antes de que expire | La desactivación de un usuario sí se aplica de inmediato (se valida en cada petición) | Lista de revocación |

## 5. Documentos relacionados

| Documento | Contenido |
|---|---|
| `README.md` | Estructura y comandos |
| `docs/modelo-datos.md` | Diagrama entidad-relación y reglas de integridad |
| `data-pipeline/README.md` | Metodología del pipeline, fuentes y reglas de limpieza |
| `docs/api-integracion.md` | Guía para el equipo de la página web (REST y WebSocket) |
| `docs/despliegue.md` | Instalador, servidor en la LAN, Docker, HTTPS y seguridad |
| `docs/evidencias/` | Resultados de la demostración de sincronización |
