# Script para iniciar el agente de Odoo Pista El Cuervo en segundo plano de forma invisible
Write-Host "Iniciando Agente Odoo Pista El Cuervo en segundo plano..." -ForegroundColor Cyan

# Comprobar que existe la carpeta C:\Utrecar
if (-not (Test-Path "C:\Utrecar")) {
    New-Item -ItemType Directory -Path "C:\Utrecar" | Out-Null
}

# Lanzar en segundo plano usando pythonw.exe
Start-Process pythonw.exe -ArgumentList "C:\Utrecar\agente_odoo_elcuervo.py" -WindowStyle Hidden

Write-Host "✅ ¡Agente corriendo en segundo plano de forma totalmente invisible!" -ForegroundColor Green
Write-Host "Logs disponibles en tiempo real en: C:\Utrecar\agente.log" -ForegroundColor Yellow
