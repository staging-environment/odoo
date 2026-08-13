Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   UTRECAR ERP - INSTALACIÓN DE PRERREQUISITOS (EL CUERVO)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Instalar Python 3.12 en Windows
Write-Host "`n[1/2] Instalando Python 3.12..." -ForegroundColor Yellow
winget install Python.Python.3.12 --override "/passive InstallAllUsers=1 PrependPath=1"

# 2. Refrescar variables de entorno en la sesión actual
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# 3. Instalar librerías de comunicación y HTTP
Write-Host "`n[2/2] Instalando librerias PySerial y Requests..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install pyserial requests

Write-Host "`n✅ ¡Prerrequisitos instalados correctamente!" -ForegroundColor Green
