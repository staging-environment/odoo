# Contexto del Proyecto: Odoo 17 ERP

Este archivo documenta la configuración del entorno, infraestructura y accesos del proyecto Odoo.

## 📌 Datos de Entornos

### 💻 Entorno Local (Desarrollo)
- **Sistema Operativo:** WSL2 Ubuntu
- **Ruta del Proyecto en WSL:** `/home/developer/Projects/odoo` (Ruta local alternativa: `/home/bonilla/Projects/odoo`)
- **Virtualización:** DDEV (`ddev start` / `ddev restart`)
- **URL Local:** `https://odoo.ddev.site` (también disponible en `http://localhost:8069`)
- **Servicios Docker:**
  - **Odoo:** versión 17.0 (`odoo:17.0`)
  - **Base de Datos:** PostgreSQL 15 (`postgres:15`) - Usuario: `db`, Password: `db`
  - **Proxy / Router:** Traefik + Nginx reverse proxy integrado en DDEV

### 🚀 Entorno de Producción
- **Usuario SSH:** `developer`
- **Dirección IP:** `164.68.101.69`

---

## 📁 Estructura del Repositorio
- `.ddev/`: Configuración del entorno virtualizado DDEV (Docker Compose y Nginx).
- `config/odoo.conf`: Archivo de configuración principal de Odoo 17.
- `extra-addons/`: Directorio para módulos y addons personalizados de Odoo.
- `AGENTS.md`: Contexto e instrucciones del proyecto para asistentes AI.
- `README.md`: Documentación general y guía rápida.

---

## 🔗 Repositorio Git
- **URL HTTPS:** `https://github.com/staging-environment/odoo`
- **URL SSH:** `git@github.com:staging-environment/odoo.git`

---

---

## ⚠️ Estado del Servicio de Sincronización en Producción (VirtusGesNet / Odoo)
- **Servicio Systemd:** `odoo-sync-stations.service` (deshabilitado e inactivo).
- **Ruta Script:** `/opt/utrecar/sync_all_stations_odoo.py` en el servidor `164.68.101.69`.
- **Logs:** `/var/log/odoo_sync_stations.log`
- **Estado:** **DESACTIVADO Y DESHABILITADO TEMPORALMENTE** en producción (`/home/developer/utrecardbs`).
- **Motivo:** Verificación de contención / bloqueos de tabla en MariaDB que afectaban a las búsquedas de clientes del TPV Aseproda (Ronda Norte).
- **Comandos de control:**
  - Activar: `systemctl enable --now odoo-sync-stations.service`
  - Desactivar: `systemctl disable --now odoo-sync-stations.service`
  - Ver logs: `journalctl -u odoo-sync-stations.service -f`
- **Documentación técnica y plan de optimización:** Ver [INCIDENCIA_SINCRONIZACION_Y_OPTIMIZACION.md](file:///home/bonilla/Projects/odoo/docs/INCIDENCIA_SINCRONIZACION_Y_OPTIMIZACION.md).
