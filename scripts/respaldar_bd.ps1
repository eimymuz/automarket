# Respaldo de la base de datos AutoMarket con pg_dump (formato custom, restaurable con pg_restore).
#
#   powershell -ExecutionPolicy Bypass -File scripts\respaldar_bd.ps1
#
# Pide la contraseña de automarket_app (o usa la variable de entorno PGPASSWORD).
# Restaurar:  pg_restore -U automarket_app -p 5433 -d automarket --clean <archivo.dump>
param(
    [string]$PgBin = "C:\Program Files\PostgreSQL\18\bin",
    [int]$Port = 5433,
    [string]$Destino = (Join-Path $PSScriptRoot "..\respaldos")
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Destino | Out-Null
$file = Join-Path (Resolve-Path $Destino) ("automarket_{0}.dump" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
& (Join-Path $PgBin "pg_dump.exe") -U automarket_app -h localhost -p $Port -d automarket -F c -f $file
if ($LASTEXITCODE -ne 0) { throw "pg_dump falló" }
Write-Host "Respaldo creado: $file ($([math]::Round((Get-Item $file).Length / 1KB)) KB)"
