# Publica el backend local en internet con un túnel de Cloudflare (HTTPS, sin tocar el router).
#
#   powershell -ExecutionPolicy Bypass -File scripts\abrir_tunel.ps1
#
# Requisitos: backend encendido en el puerto 8000 y cloudflared instalado
#   (winget install --id Cloudflare.cloudflared).
# La dirección *.trycloudflare.com cambia cada vez que se abre el túnel: compártela de nuevo.
# Ctrl+C cierra el túnel.
param(
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"

$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
if (-not (Test-Path $cf)) { throw "No se encontró cloudflared. Instálalo con: winget install --id Cloudflare.cloudflared" }

try {
    Invoke-RestMethod "http://localhost:$Port/api/v1/health" -TimeoutSec 5 | Out-Null
} catch {
    throw "El backend no responde en http://localhost:$Port. Enciéndelo primero (uvicorn app.main:app --port $Port)."
}

$log = Join-Path $env:TEMP "automarket-tunel.log"
Remove-Item $log -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath $cf -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:$Port" `
    -PassThru -WindowStyle Hidden -RedirectStandardError $log

try {
    $url = $null
    for ($i = 0; $i -lt 40 -and -not $url; $i++) {
        Start-Sleep -Seconds 1
        $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($m) { $url = $m.Matches[0].Value }
    }
    if (-not $url) { throw "No se obtuvo la dirección del túnel; revisa $log" }

    $ws = $url -replace "^https", "wss"
    Write-Host ""
    Write-Host "Túnel abierto. Comparte estas direcciones con el otro equipo:" -ForegroundColor Green
    Write-Host "  API:            $url/api/v1"
    Write-Host "  WebSocket:      $ws/api/v1/ws"
    Write-Host "  Documentación:  $url/docs"
    Write-Host ""
    Write-Host "En AutoMarket.exe: Servidor · cambiar -> $url"
    Write-Host "Deja esta ventana abierta. Ctrl+C cierra el túnel." -ForegroundColor Yellow
    $proc.WaitForExit()
} finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    Write-Host "Túnel cerrado."
}
