# Convierte esta computadora en el servidor central de AutoMarket (ejecutar como ADMINISTRADOR).
#
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_servidor.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_servidor.ps1 -Desinstalar
#
# - Registra la tarea programada "AutoMarket Backend": arranca al encender Windows (aunque nadie
#   inicie sesión) y se reinicia sola si falla.
# - Abre el puerto 8000 en el Firewall de Windows solo para redes PRIVADAS (LAN), no públicas.
# PostgreSQL ya está instalado como servicio de Windows y NO se expone: solo el backend lo usa.
param(
    [switch]$Desinstalar,
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$taskName = "AutoMarket Backend"
$ruleName = "AutoMarket API (TCP $Port)"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Ejecuta PowerShell como Administrador (clic derecho > Ejecutar como administrador)." }

if ($Desinstalar) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    Write-Host "Tarea y regla de firewall eliminadas."
    return
}

$script = Join-Path $PSScriptRoot "iniciar_backend.ps1" | Resolve-Path
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -Port $Port"
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT30S"   # da tiempo a que arranque el servicio de PostgreSQL
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description "API central de AutoMarket (FastAPI) para AutoMarket.exe y la página web" -Force | Out-Null

if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port `
        -Action Allow -Profile Private | Out-Null
}

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 8
# La IP útil es la del adaptador con puerta de enlace (no las de adaptadores virtuales)
$lan = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" }
Write-Host "`nServidor AutoMarket instalado. Arranca solo con Windows."
foreach ($cfg in $lan) {
    Write-Host ("  http://{0}:{1}/docs   ({2})" -f $cfg.IPv4Address.IPAddress, $Port, $cfg.InterfaceAlias)
}
try {
    $h = Invoke-RestMethod "http://localhost:$Port/api/v1/health" -TimeoutSec 10
    Write-Host "  Estado: API $($h.api) · base de datos $($h.database.status)"
} catch {
    Write-Warning "La API aún no responde; revisa backend\logs\backend.log"
}
