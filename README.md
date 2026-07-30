# Odoo 17 ERP - Staging Environment

Repositorio del proyecto Odoo 17 virtualizado con DDEV para desarrollo local y despliegue en producción.

## 🚀 Inicio Rápido en Local (DDEV)

### Requisitos
- WSL2 (Ubuntu)
- Docker Desktop
- DDEV v1.23+

### Arrancar el entorno
```bash
ddev start
```

Acceso al servicio:
- **URL Web (HTTPS):** [https://odoo.ddev.site](https://odoo.ddev.site)
- **Puerto Odoo Directo:** `http://localhost:8069`
- **Mailpit:** `https://odoo.ddev.site:8026`

---

## 🛠️ Detalles del Entorno

### Local (WSL Ubuntu)
- **Ruta WSL:** `/home/developer/Projects/odoo` (o `/home/bonilla/Projects/odoo`)
- **Versión Odoo:** 17.0
- **Base de Datos:** PostgreSQL 15 (Host: `db`, Port: `5432`, User: `db`, Password: `db`)

### Producción
- **Servidor IP:** `164.68.101.69`
- **Usuario:** `developer`

---

## 📂 Añadir Módulos / Addons Personalizados
Coloca los nuevos módulos en el directorio `./extra-addons/`. Odoo los detectará automáticamente al reiniciar el servicio o actualizar la lista de aplicaciones.
