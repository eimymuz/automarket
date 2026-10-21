# Despliegue de AutoMarket

```
            ┌──────────────── Servidor central (siempre encendido) ────────────────┐
 AutoMarket.exe ──HTTP/WS──►│  AutoMarket API (FastAPI, puerto 8000)  ──►  PostgreSQL (5433, local)  │
 Página web     ──HTTP/WS──►│  tarea programada o contenedor Docker        no se expone a la red     │
            └───────────────────────────────────────────────────────────────────────┘
```

- **AutoMarket.exe** es solo un cliente. Se instala en cualquier PC de la agencia y no necesita
  Node.js, Python ni PostgreSQL.
- **El backend** corre en UNA computadora o servidor que permanece encendido. Debe estar disponible
  aunque nadie tenga AutoMarket.exe abierto, porque la página web también depende de él.
- **PostgreSQL** solo acepta conexiones del backend. Ningún cliente se conecta directamente a la base.

Hay tres escenarios, de menor a mayor alcance:

| Escenario | Para qué | Cómo |
|---|---|---|
| 1. Local | Desarrollo y pruebas | `uvicorn app.main:app --reload` en `localhost:8000` |
| 2. Red local (LAN) | Ambos equipos en la misma red (escuela o casa) | Tarea programada de Windows (abajo) |
| 3. Internet | Equipos en redes distintas | Docker en un VPS + HTTPS (abajo) |

---

## 1. Instalar AutoMarket.exe

1. Copia `desktop\release\AutoMarket-Setup-1.0.0.exe` a la PC de la agencia y ejecútalo.
2. **Advertencia de SmartScreen:** el instalador no tiene firma digital (un certificado de firma de
   código cuesta dinero). Pulsa **Más información → Ejecutar de todas formas**.
3. Se instala para el usuario actual, sin permisos de administrador, y crea accesos directos en el
   escritorio y en el menú Inicio.
4. En la pantalla de inicio de sesión pulsa **"Servidor: … · cambiar"** y escribe la dirección del
   backend, por ejemplo `http://192.168.100.6:8000`. Pulsa **Probar conexión** y luego **Guardar**.
   La dirección queda guardada en `%APPDATA%\AutoMarket\config.json`.

Regenerar el instalador después de cambiar el código:

```powershell
cd desktop
npm run dist          # -> desktop\release\AutoMarket-Setup-<versión>.exe
```

---

## 2. Servidor en la red local (recomendado para el proyecto)

En la computadora que funcionará como servidor, que necesita PostgreSQL 18, el entorno `backend\.venv`
y la base ya cargada (etapas 1-3):

### 2.1 Configuración de producción (`backend\.env`)

```ini
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://automarket_app:<contraseña>@localhost:5433/automarket
JWT_SECRET=<secreto largo y aleatorio>
# Origen de la página web del otro equipo (protocolo + host + puerto), separados por coma
CORS_ORIGINS=http://localhost:5173,http://192.168.100.20:3000
```

> En modo `production` la API **no arranca** si `JWT_SECRET` sigue con el valor por defecto.

### 2.2 Instalarlo como servicio

Abre PowerShell **como Administrador**:

```powershell
cd "<ruta>\automarket"
powershell -ExecutionPolicy Bypass -File scripts\instalar_servidor.ps1
```

El script:

- Registra la tarea **"AutoMarket Backend"**: arranca al encender Windows, aunque nadie inicie sesión,
  y se reinicia sola si falla. Ejecuta `scripts\iniciar_backend.ps1`, que aplica las migraciones
  pendientes y levanta uvicorn en `0.0.0.0:8000` con un solo worker.
- Abre el puerto **8000 solo para redes privadas** en el Firewall de Windows.
- Muestra las direcciones para compartir, por ejemplo `http://192.168.100.6:8000/docs`.

| Acción | Comando |
|---|---|
| Ver el log | `Get-Content backend\logs\backend.log -Tail 50 -Wait` |
| Reiniciar | `Restart-ScheduledTask "AutoMarket Backend"` (o reinicia la PC) |
| Desinstalar | `scripts\instalar_servidor.ps1 -Desinstalar` |
| Respaldar la BD | `scripts\respaldar_bd.ps1` → `respaldos\automarket_<fecha>.dump` |

**Importante:**
- Configura la red Wi-Fi como **privada**. Si es pública, el firewall bloquea el puerto.
- Reserva una IP fija para el servidor en el router, o avisa al otro equipo si cambia.
- Recomendado: mueve el proyecto fuera de OneDrive (por ejemplo a `C:\AutoMarket`) en la PC servidor.
  La sincronización de OneDrive puede bloquear archivos mientras el servicio los usa.
- No ejecutes el servidor de desarrollo (`uvicorn --reload` en el puerto 8000) al mismo tiempo que el servicio.

### 2.3 Lo que se le entrega al otro equipo

- URL base: `http://<IP-del-servidor>:8000/api/v1`
- Documentación: `http://<IP-del-servidor>:8000/docs` y `docs/api-integracion.md`
- Se les pide el origen de su página para agregarlo a `CORS_ORIGINS`.

---

## 3a. Acceso por internet desde tu PC (túnel de Cloudflare)

Para que un equipo en otra red se conecte sin abrir puertos del router. Tu PC debe estar encendida.

```powershell
winget install --id Cloudflare.cloudflared                          # una sola vez
powershell -ExecutionPolicy Bypass -File scripts\abrir_tunel.ps1    # con el backend encendido
```

El script muestra una dirección `https://<palabras>.trycloudflare.com`. Desde ella funcionan la API
(`/api/v1`), el WebSocket (`wss://…/api/v1/ws`) y Swagger (`/docs`). La dirección **cambia cada vez**
que se abre el túnel; para una dirección fija se necesita un dominio propio con un túnel con nombre de
Cloudflare, o el despliegue en la nube (abajo). Agrega el origen público de la página web a `CORS_ORIGINS`.

## 3b. Servidor en internet (Docker)

Para un VPS (Linux) o cualquier equipo con Docker. La imagen incluye Python y la base PostgreSQL
corre en su propio contenedor, **sin publicar su puerto**.

```bash
cp .env.docker.example .env        # editar DB_PASSWORD, JWT_SECRET, CORS_ORIGINS
docker compose up -d --build       # base de datos + API (aplica migraciones al arrancar)
docker compose --profile seed run --rm seed    # carga inicial: pipeline transform→generate→load→stats
docker compose exec api python -m app.cli create-admin --email admin@automarket.mx
```

El servicio `seed` reutiliza el HTML ya descargado en `data-pipeline/raw/`, así que no vuelve a hacer
scraping, y deja sus evidencias en `data-pipeline/evidence/`.

**HTTPS:** en internet, pon un proxy inverso con certificado delante de la API. Por ejemplo, Caddy
obtiene el certificado de Let's Encrypt automáticamente:

```
api.tu-dominio.mx {
    reverse_proxy localhost:8000     # también reenvía los WebSockets (wss://)
}
```

Así los clientes usan `https://api.tu-dominio.mx` y `wss://api.tu-dominio.mx/api/v1/ws`.

---

## Lista de seguridad antes de compartir el servidor

- [ ] `JWT_SECRET` propio y `ENVIRONMENT=production`.
- [ ] Contraseña propia para `automarket_app`, que no esté en ningún archivo compartido.
- [ ] `CORS_ORIGINS` solo con los orígenes reales de la web.
- [ ] PostgreSQL sin acceso desde la red. En Docker ya está resuelto (no publica puertos). En la
      instalación nativa, PostgreSQL 18 escucha por defecto en **todas** las interfaces (`0.0.0.0:5433`).
      Su `pg_hba.conf` predeterminado solo autoriza conexiones locales, pero conviene cerrarlo del todo:
      como Administrador, edita `C:\Program Files\PostgreSQL\18\data\postgresql.conf`, cambia
      `listen_addresses = '*'` por `listen_addresses = 'localhost'` y reinicia el servicio con
      `Restart-Service postgresql-x64-18`. Verifica con `Get-NetTCPConnection -State Listen -LocalPort 5433`:
      solo deben aparecer `127.0.0.1` y `::1`.
- [ ] Desactivados los usuarios de prueba (`verificacion.temporal@…`) y, si no se usa, el cliente demo.
- [ ] Respaldo programado de la base (`scripts\respaldar_bd.ps1`).
- [ ] Un solo worker de uvicorn: el difusor de WebSockets vive en memoria. Para escalar a varios
      workers habría que usar PostgreSQL LISTEN/NOTIFY o Redis.
