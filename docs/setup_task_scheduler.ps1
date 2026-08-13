# Script de automatización para registrar la Tarea Programada de Windows en el PC de caja
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   UTRECAR ERP - CONFIGURACIÓN PROGRAMADOR DE TAREAS 24/7" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Asegurar carpeta C:\Utrecar
if (-not (Test-Path "C:\Utrecar")) {
    New-Item -ItemType Directory -Path "C:\Utrecar" | Out-Null
    Write-Host "[+] Creada carpeta C:\Utrecar" -ForegroundColor Yellow
}

# 2. Copiar script de producción a C:\Utrecar si existe localmente
if (Test-Path ".\agente_odoo_elcuervo.py") {
    Copy-Item ".\agente_odoo_elcuervo.py" "C:\Utrecar\agente_odoo_elcuervo.py" -Force
    Write-Host "[+] Copiado agente_odoo_elcuervo.py a C:\Utrecar\" -ForegroundColor Yellow
}

# 3. Registrar Tarea Programada en Windows (Sobrevivir a reinicios del PC)
$TaskName = "AgenteOdooElCuervo"
$ScriptPath = "C:\Utrecar\agente_odoo_elcuervo.py"

Write-Host "`n[+] Registrando tarea '$TaskName' en el Programador de Tareas..." -ForegroundColor Yellow

# Comando universal via schtasks
schtasks /Create /TN $TaskName /TR "pythonw.exe $ScriptPath" /SC ONSTART /RU "SYSTEM" /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ ¡Tarea Programada creada con éxito!" -ForegroundColor Green
    Write-Host "El agente de Odoo Pista se ejecutará automáticamente cada vez que se encienda o reinicie el PC." -ForegroundColor Green
} else {
    # Intento secundario al iniciar sesión de usuario
    schtasks /Create /TN $TaskName /TR "pythonw.exe $ScriptPath" /SC ONLOGON /F
    Write-Host "`n✅ Tarea creada para inicio de sesión (ONLOGON)." -ForegroundColor Green
}
