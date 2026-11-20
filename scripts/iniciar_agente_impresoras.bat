@echo off
rem Publica en Odoo las impresoras instaladas en este PC (tarea programada AgenteImpresorasOdoo)
cd /d C:\Utrecar
"C:\Program Files\Python312\pythonw.exe" C:\Utrecar\agente_impresoras_pista.py >> C:\Utrecar\agente_impresoras.log 2>&1
