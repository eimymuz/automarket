# 🚗 AutoMarket

### Sistema de Administración de una Agencia de Compraventa de Automóviles

**AutoMarket** es un sistema desarrollado como proyecto de la materia de Ingeniería de Datos, cuyo objetivo es administrar el inventario, las reservas, las compras y las ventas de una agencia automotriz mediante una arquitectura centralizada.

El proyecto integra una aplicación de escritorio para administradores, una API REST para la comunicación con clientes externos y un pipeline de Ingeniería de Datos encargado de recopilar, transformar y almacenar información automotriz.

## Tecnologías utilizadas

| Componente | Tecnologías |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Base de datos | PostgreSQL 18 |
| Aplicación de escritorio | Electron, React, TypeScript, Vite |
| Ingeniería de Datos | Python, Pandas, NumPy, httpx |
| Autenticación | JWT, bcrypt |
| Comunicación | REST API, WebSockets |
| Visualización | Recharts |
| Despliegue | Docker Compose, electron-builder |

## Arquitectura del sistema

AutoMarket utiliza una arquitectura centralizada donde todos los componentes interactúan con una misma base de datos mediante el backend.

```text
           AutoMarket
               |
     +---------+---------+
     |                   |
 Aplicación           Página web
 de escritorio        externa
     |                   |
     +---------+---------+
               |
          REST API
           FastAPI
               |
          PostgreSQL
               ^
               |
       Pipeline de datos
      Extracción y limpieza
```

La aplicación de escritorio está destinada a los administradores de la agencia. La página web para clientes es desarrollada por otro equipo y utiliza la API de AutoMarket para consultar vehículos y realizar operaciones.

## Estructura del proyecto

```text
automarket/
|
|-- backend/
|   |-- app/
|   |-- alembic/
|   |-- tests/
|
|-- desktop/
|
|-- data-pipeline/
|
|-- docs/
|
|-- scripts/
|
|-- docker-compose.yml
|-- README.md
```

| Carpeta | Descripción |
|---|---|
| `backend/` | API central, autenticación, modelos y lógica de negocio |
| `desktop/` | Aplicación de escritorio desarrollada con Electron y React |
| `data-pipeline/` | Extracción, limpieza, transformación y carga de datos |
| `docs/` | Documentación técnica y guías de integración |
| `scripts/` | Scripts SQL, configuración y utilidades de despliegue |

## Funcionalidades principales

### Administración de vehículos

- Registro de nuevos automóviles.
- Edición y eliminación lógica de vehículos.
- Administración de fotografías.
- Búsqueda, filtros y paginación.
- Control de disponibilidad.
- Historial de operaciones.

### Reservas y ventas

- Gestión de reservas de vehículos.
- Cancelación y vencimiento automático de reservas.
- Simulación de compras y pagos.
- Confirmación administrativa de ventas.
- Control de concurrencia para evitar operaciones duplicadas.

### Panel de administración

- Dashboard con indicadores generales.
- Estadísticas de inventario.
- Gráficas interactivas.
- Actividad reciente.
- Sincronización de información mediante WebSockets.

### Ingeniería de Datos

El sistema incorpora un pipeline que realiza:

1. Extracción de información de catálogos automotrices.
2. Almacenamiento de datos originales.
3. Identificación de duplicados y valores faltantes.
4. Limpieza y normalización mediante Pandas.
5. Validación de tipos y reglas de calidad.
6. Generación de estadísticas y evidencias.
7. Carga de información en PostgreSQL.

El catálogo documentado contiene **121 vehículos**, incluyendo registros obtenidos de catálogos oficiales y unidades de referencia derivadas de estos datos.

## Requisitos

Para ejecutar el proyecto en un entorno de desarrollo se requiere:

- Node.js 24
- Python 3.12
- PostgreSQL 18
- npm
- Git

En el entorno original de desarrollo, PostgreSQL utiliza el puerto `5433`.

## Instalación y configuración

### 1. Clonar el repositorio

```powershell
git clone https://github.com/eimymuz/automarket.git
cd automarket
```

### 2. Configurar PostgreSQL

Crear la base de datos ejecutando:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -p 5433 -f .\scripts\create_database.sql
```

Configurar la conexión a PostgreSQL en el archivo:

`backend/.env`

La variable `DATABASE_URL` debe contener los datos correspondientes al entorno local.

No se deben publicar contraseñas ni credenciales en el repositorio.

### 3. Ejecutar el backend

Acceder a la carpeta:

```powershell
cd backend
```

Activar el entorno virtual existente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Iniciar el servidor:

```powershell
uvicorn app.main:app --reload --port 8000
```

Servicios disponibles:

- API: http://localhost:8000
- Documentación Swagger: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health

### 4. Crear un administrador

Desde la carpeta `backend`, ejecutar:

```powershell
python -m app.cli create-admin --email admin@automarket.mx --name "Administrador"
```

La contraseña se solicitará de manera segura en la terminal.

### 5. Ejecutar la aplicación de escritorio

Desde la raíz del proyecto:

```powershell
cd desktop
npm install
npm run dev
```

La aplicación de escritorio se comunica con el backend mediante la API REST y WebSockets.

## Pruebas

AutoMarket incorpora pruebas automatizadas para validar el funcionamiento del sistema.

| Componente | Pruebas documentadas |
|---|---:|
| Backend | 44 |
| Pipeline de datos | 22 |
| Sincronización | 8 verificaciones |

Ejecutar pruebas del backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas contemplan autenticación, vehículos, reservas, compras, seguridad, concurrencia y comunicación en tiempo real.

## Despliegue

### Aplicación de escritorio para Windows

```powershell
cd desktop
npm run dist
```

Instalador generado según la configuración documentada:

`desktop/release/AutoMarket-Setup-1.0.0.exe`

### Servidor en red local

Ejecutar el script de instalación del servidor con permisos de administrador:

`scripts/instalar_servidor.ps1`

### Docker Compose

```powershell
docker compose up -d --build
```

La configuración de Docker debe verificarse en el entorno donde se realizará el despliegue.

## Seguridad

AutoMarket incorpora diferentes mecanismos de protección:

- Autenticación mediante JWT.
- Roles de administrador y cliente.
- Validación de datos con Pydantic.
- Restricciones de integridad en PostgreSQL.
- Auditoría de operaciones.
- Control de concurrencia en reservas.
- Validación de archivos de imagen.
- Configuración de orígenes permitidos mediante CORS.

Los pagos son simulados y el sistema no almacena números de tarjetas bancarias.

## Documentación técnica

Para conocer más detalles sobre la implementación, consultar:

- [Informe técnico](docs/INFORME_TECNICO.md)
- [Modelo de datos](docs/modelo-datos.md)
- [Integración de la API](docs/api-integracion.md)
- [Guía de despliegue](docs/despliegue.md)
- [Pipeline de datos](data-pipeline/README.md)

## Estado del proyecto

AutoMarket cuenta con una aplicación de escritorio, una API central, un modelo de datos relacional y un pipeline de Ingeniería de Datos.

La integración con la página web externa está contemplada mediante los endpoints REST y el sistema de eventos en tiempo real.

## Contexto académico

**Proyecto:** AutoMarket  
**Materia:** Ingeniería de Datos  
**Institución:** Tecnológico de Colima  
**Repositorio:** https://github.com/eimymuz/automarket

---

Desarrollado con fines académicos para integrar conocimientos de Ingeniería de Datos, desarrollo de software, bases de datos y comunicación entre sistemas.
