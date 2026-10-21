# AutoMarket

Sistema de administración de una agencia de compraventa de automóviles.

| Carpeta          | Contenido                                                   |
|------------------|-------------------------------------------------------------|
| `backend/`       | API central FastAPI + SQLAlchemy + Alembic (PostgreSQL)     |
| `desktop/`       | AutoMarket.exe: Electron + Vite + React + TypeScript        |
| `data-pipeline/` | Pipeline de Ingeniería de Datos con Pandas (raw → processed)|
| `docs/`          | Documentación técnica e integración para el equipo web      |
| `scripts/`       | Scripts SQL y utilidades                                    |

## Requisitos
- Node.js 24, Python 3.12, PostgreSQL 18 (puerto **5433** en este equipo)

## Base de datos (una sola vez)
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -p 5433 -f .\scripts\create_database.sql
```
Después coloca la misma contraseña en `backend\.env` (`DATABASE_URL`).

## Backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
# Salud:   http://localhost:8000/api/v1/health
# Swagger: http://localhost:8000/docs
pytest -q
# Crear un administrador (pide la contraseña de forma oculta):
python -m app.cli create-admin --email admin@automarket.mx --name "Administrador"
```

## Escritorio
```powershell
cd desktop
npm install
npm run dev
```

## Despliegue

- Instalador de Windows: `cd desktop; npm run dist` → `desktop\release\AutoMarket-Setup-1.0.0.exe`
- Servidor en la red local: `scripts\instalar_servidor.ps1` (como Administrador)
- Docker / internet: `docker compose up -d --build`
- Guía completa: [docs/despliegue.md](docs/despliegue.md) · Integración del equipo web: [docs/api-integracion.md](docs/api-integracion.md)