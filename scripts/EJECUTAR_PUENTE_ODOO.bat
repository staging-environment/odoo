@echo off
title UTRECAR ERP - Puente Pista a Odoo Cloud (E.S. Repsol)
cd /d "%~dp0"
echo ========================================================
echo   Iniciando Agente Puente Pista a Odoo Cloud
echo   Estacion: E.S. Repsol (https://odoo.utrecar.com)
echo ========================================================
echo.
python agente_pista_odoo_bridge.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocurrio un error al ejecutar Python.
    pause
)
