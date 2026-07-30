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
