# Contexto del Proyecto: Odoo 17 ERP

Este archivo documenta la configuración del entorno, infraestructura, accesos y la integración de datos de Aseproda en el proyecto Odoo.

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
- **Servidor Cloud:** `https://odoo.utrecar.com`
- **Usuario SSH:** `root` / `developer`
- **Dirección IP:** `164.68.101.69`
- **Base de Datos Aseproda:** MariaDB / MySQL 5.5 en puerto `33061` (Contenedor `ddev-utrecar3-db`)
- **Ruta Bases de Datos Aseproda:** `/home/developer/Projects/utrecardbs`

---

## 🛢️ Integración Aseproda ➔ Odoo Cloud

Las bases de datos operativas de Aseproda se encuentran en `/home/developer/Projects/utrecardbs`:
- **`virtusgesnet`**:
  - `clientes`: 1.811 clientes (`res.partner`, `ref: ASEPRODA-{Codigo}`).
  - `proveedores`: 483 proveedores (`res.partner`, `ref: PROV-{Codigo}`).
  - `facturasyticketsdeventa` & `detalledefacturasyticketsdeventa`: Facturas oficiales a clientes (`account.move` tipo `out_invoice`, series `FR...`, `FT...`, `FC...`, `FG...`).
  - `facturasdecompra` & `detalledefacturasdecompra`: Facturas de compra de carburante y tienda (`account.move` tipo `in_invoice`).
  - `almacenesytanques`: 14 almacenes y tanques de las 4 gasolineras.
  - `detallederegularizacionesdealmacen`: Aforos y recuentos físicos para stock.
- **`administracioncorporativa`**: Configuración de perfiles, usuarios e informes.
- **`sii`**: Suministro Inmediato de Información a la AEAT.

### Estructura de Inventario y Almacenes en Odoo:
- **Almacenes (`stock.warehouse`):**
  - `E.S. Utrera` (`UTR`)
  - `E.S. Atalaya` (`ATE`)
  - `E.S. Rodalabota` (`RO`)
  - `E.S. Ronda Norte` (`RN`)
- **Ubicaciones:** Tanques de Gasóleo A (`TK_*_GAS_A`), Sin Plomo 95 (`TK_*_SP95`) y Tienda (`TIENDA_*`).
- **Existencias inicializadas (`stock.quant`):** Litros y unidades de recuentos físicos aplicados en cada estación.

---

## 🛠️ Scripts y Herramientas del Proyecto

- `scripts/migrate_aseproda_to_odoo.py`: Importador optimizado de clientes y facturas con precarga en memoria y consultas indexadas.
- `scripts/cleanup_aseproda_test_data.py`: **Herramienta de purga total** para eliminar de forma segura facturas, quants de inventario, proveedores y clientes de prueba, restaurando Odoo a su estado limpio.
- `docs/INTEGRACION_ASEPRODA_ODOO.md`: Documentación técnica detallada de la integración.

### Comandos Clave:
```bash
# Sincronizar clientes y facturación de 2026:
python3 scripts/migrate_aseproda_to_odoo.py --all

# Simular borrado de pruebas:
python3 scripts/cleanup_aseproda_test_data.py --dry-run

# Confirmar y purgar todos los datos de prueba de Aseproda en Odoo:
python3 scripts/cleanup_aseproda_test_data.py --confirm
```

---

## 📁 Estructura del Repositorio
- `.ddev/`: Configuración del entorno virtualizado DDEV.
- `config/odoo.conf`: Archivo de configuración de Odoo 17.
- `extra-addons/`: Módulos y addons personalizados.
- `scripts/`: Scripts de integración, mantenimiento y purga.
- `docs/`: Guías de arquitectura, hojas de ruta y diagnósticos.
- `AGENTS.md`: Contexto e instrucciones del proyecto.
- `README.md`: Documentación general.

---

## 🔗 Repositorio Git
- **URL HTTPS:** `https://github.com/staging-environment/odoo`
- **URL SSH:** `git@github.com:staging-environment/odoo.git`

---

## ⚠️ Estado del Servicio de Sincronización en Producción (VirtusGesNet / Odoo)
- **Servicio Systemd:** `odoo-sync-stations.service` (deshabilitado temporalmente para comprobación de bloqueos MyISAM).
- **Ruta Script:** `/opt/utrecar/sync_all_stations_odoo.py` en el servidor `164.68.101.69`.
- **Logs:** `/var/log/odoo_sync_stations.log`
- **Documentación técnica:** Ver [INCIDENCIA_SINCRONIZACION_Y_OPTIMIZACION.md](file:///home/bonilla/Projects/odoo/docs/INCIDENCIA_SINCRONIZACION_Y_OPTIMIZACION.md).
