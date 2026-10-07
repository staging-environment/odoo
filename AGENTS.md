# Contexto del Proyecto: Odoo 17 ERP - UTRECAR

Este archivo documenta la configuración del entorno, infraestructura, accesos, arquitectura de hardware de pista y la integración de datos de Aseproda en el proyecto Odoo.

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

## ⛽ Arquitectura de Pista y Estrategia de Control (IMPORTANTE)

### 1. Conexión Física Actual:
- **Sin hardware DOMS:** Las estaciones cuentan con **conexión directa** de los surtidores a los puertos serie / concentrador local en el PC de la estación (`SDES.exe` / puertos COM).
- **Puente en tiempo real:** El script `scripts/agente_pista_odoo_bridge.py` monitoriza en tiempo real los eventos de pista (`dw.log` y base de datos local) y los traslada a Odoo Cloud (`pos_gas_station`).

### 2. Estrategia y Hoja de Ruta Acordada:
1. **Fase Actual (Prioridad Absoluta):** Afinar al 100% toda la operativa funcional de Odoo (ventas de tienda, combos, cobros, facturación con matrícula/conductor, envío por email, clientes de crédito y arqueos). Mantener el modo puente/espejo estable sin alterar la conexión física de pista.
2. **Fase Futura Planificada:** Cuando la operativa de Odoo esté completamente afinada y validada en producción, **Odoo asumirá el rol de MÁSTER directo de pista sobre la conexión directa existente**, prescindiendo y apagando definitivamente VirtusTPV.

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

- `scripts/agente_pista_odoo_bridge.py`: Agente puente en tiempo real entre la pista local (conexión directa) y Odoo Cloud.
- `scripts/migrate_aseproda_to_odoo.py`: Importador optimizado de clientes y facturas con precarga en memoria y consultas indexadas.
- `scripts/cleanup_aseproda_test_data.py`: **Herramienta de purga total** para eliminar de forma segura facturas, quants de inventario, proveedores y clientes de prueba, restaurando Odoo a su estado limpio.
- `docs/HISTORICO_PROYECTO_UTRECAR.md`: Histórico técnico completo de cambios, módulos y despliegues.
- `docs/INFORME_Y_GUIA_OPERATIVA_VENTAS_TPV_UTRECAR.md`: Guía de operativa táctil para el cajero.

---

## 📁 Estructura del Repositorio
- `.ddev/`: Configuración del entorno virtualizado DDEV.
- `config/odoo.conf`: Archivo de configuración de Odoo 17.
- `extra-addons/`: Módulos personalizados (`pos_gas_station`, `utrecar_invoice_vehicle`).
- `scripts/`: Scripts de integración, mantenimiento y puente de pista.
- `docs/`: Guías de arquitectura, hojas de ruta, informes PDF y diagnósticos.
- `AGENTS.md`: Contexto e instrucciones clave del proyecto.
- `README.md`: Documentación general.

---

## 🔗 Repositorio Git
- **URL HTTPS:** `https://github.com/staging-environment/odoo`
- **URL SSH:** `git@github.com:staging-environment/odoo.git`
