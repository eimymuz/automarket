# Inicia el backend central de AutoMarket en modo servidor (accesible desde la red local).
#
#   powershell -ExecutionPolicy Bypass -File scripts\iniciar_backend.ps1
#
# 1. Aplica migraciones pendientes (alembic upgrade head).
# 2. Arranca uvicorn en 0.0.0.0:8000 con UN worker (el difusor de WebSockets vive en memoria).
# La salida se guarda en backend\logs\backend.log.
param(
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend" | Resolve-Path
$python = Join-Path $backend ".venv\Scripts\python.exe"
$logDir = Join-Path $backend "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "backend.log"

Set-Location $backend
$env:PYTHONIOENCODING = "utf-8"
"$(Get-Date -Format s) ==== Iniciando AutoMarket API en el puerto $Port" | Out-File -Append -Encoding utf8 $log

# Alembic y uvicorn escriben su log en stderr. En PowerShell 5.1 cada línea de stderr llega como un
# "error"; con ErrorActionPreference=Continue se convierte a texto y se agrega al archivo.
$ErrorActionPreference = "Continue"
function Invoke-Logged {
    & $python @args 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log
    return $LASTEXITCODE
}

if ((Invoke-Logged -m alembic upgrade head) -ne 0) { throw "Falló la migración de la base de datos; revisa $log" }
Invoke-Logged -m uvicorn app.main:app --host 0.0.0.0 --port $Port --workers 1 --proxy-headers --log-level info | Out-Null
