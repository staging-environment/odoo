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
- **Ruta Odoo en Cloud:** `/home/developer/Projects/odoo`
- **Contenedor Odoo en Cloud:** `ddev-odoo-odoo`
- **Base de Datos Aseproda:** MariaDB / MySQL 5.5 en puerto `33061` (Contenedor `ddev-utrecar3-db`)
- **Ruta Bases de Datos Aseproda:** `/home/developer/Projects/utrecardbs`

### ⛽ Servidores Windows de Pista (Acceso SSH Directo 24/7)
- **E.S. Repsol (Trieste / SE-30 Calonge):**
  - **IP WireGuard VPN:** `10.8.0.18` (IP Local alternativa: `192.168.8.9`)
  - **Usuario:** `usuario` (`desktop-qlqikag\usuario`)
  - **Puerto SSH:** `22` (OpenSSH Windows Service)
  - **Acceso:** Clave pública RSA directa sin contraseña (`ssh usuario@10.8.0.18`)
  - **Hardware de Pista:** Surtidores Wayne DART en `COM3` (9600 bps) vía `C:\SDES\SDES.exe`
  - **Control Nativo por Socket:** `ClienteSDESNet.dll` (puerto TCP `8777`, clase `ClienteSDES2`)
  - **Modo de Trabajo:** `C:\SDES\ModoTrabajo.ini` (0=Atendido, 1=Postpago, 2=Prepago)
  - **Agente Odoo Pista:** `C:\agente_pista_odoo_bridge.py`
  - **Arranque Invisible 24/7:**
    - Tarea programada `AgenteOdooRepsol`: ejecuta `C:\Utrecar\iniciar_agente_odoo.bat` (con `pythonw.exe`) a nivel de arranque del sistema (`BootTrigger`) bajo cuenta `SYSTEM` (Sesión 0, 100% invisible para el cajero).
    - Tarea programada `RunSDES`: arranca `C:\SDES\arrancar_sdes.bat` a nivel de arranque del sistema (`SYSTEM`).
    - Desactivado arranque automático de `VirtusTPV` y `Administracion Corporativa` en registro de Windows.
    - Acceso directo en escritorio: `Odoo TPV - Gasolinera Repsol.lnk` para apertura en modo aplicación de `https://odoo.utrecar.com/pos/ui?config_id=7`.
  - **Documentación detallada:** `docs/ACCESO_REMOTO_PISTA_REPSOL_TRIESTE.md`

---

## ⛽ Arquitectura de Pista y Estrategia de Control (IMPORTANTE)

### 1. Conexión Física y Protocolo Nativo:
- **Sin hardware DOMS:** Las estaciones cuentan con **conexión directa** de los surtidores a los puertos serie / concentrador local en el PC de la estación (`SDES.exe` en `COM3` a 9600 bps).
- **Control MÁSTER en Tiempo Real:** 
  - Odoo POS asume el rol MÁSTER completo sobre la pista.
  - El agente `scripts/agente_pista_odoo_bridge.py` se comunica con el servidor local SDES en `127.0.0.1:8777` usando la librería nativa `ClienteSDESNet.dll` vía `pythonnet`.
  - Permite desbloquear (`Desbloquear(calle)`), bloquear (`Bloquear(calle)`) y cambiar modo de trabajo (`CambiarModoTrabajo(calle, modo)`) de forma inmediata con 0 ms de latencia.
- **Flujo de Autorizaciones Remotas desde el TPV de Odoo Cloud:**
  1. En el frontend de Odoo POS (`extra-addons/pos_gas_station`), el cajero pulsa "AUTORIZAR" o selecciona importe/litros.
  2. El controlador `/pos_gas_station/authorize` emite el comando a través de `ir.config_parameter` (`pos_gas_station.pump_command_7`).
  3. El agente de pista local captura la orden en milisegundos, invoca `ClienteSDES2.Desbloquear(calle)` y conmuta a `ATENDIDO`.
  4. El surtidor físico arranca y despacha el combustible.
  5. Al colgar la manguera, `dw.log` y MySQL detectan el fin de venta; el agente bloquea la manguera (`Bloquear(calle)` / `PREPAGO`) y traslada la venta al TPV de Odoo en estado "PENDIENTE DE COBRO".
- **Prueba Física Real Confirmada:**
  - Calle 8 (Diésel) suministró 2.15L (3.85 €) y apareció al instante en pantalla del TPV lista para cobro con un clic.

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

### Mapeo de Combustibles (E.S. Repsol / Config ID 7):
- **Gasóleo A:** ID Odoo `51` (código `GAS_A` / `GA`)
- **Sin Plomo 95:** ID Odoo `52` (código `SP95` / `95`)
- **Gasóleo Plus:** ID Odoo `54` (código `GAS_PLUS` / `G+`)

---

## 🛠️ Scripts y Herramientas del Proyecto

- `scripts/agente_pista_odoo_bridge.py`: Agente puente resiliente 24/7 con integración nativa `ClienteSDES2` y watchdog de reconexión.
- `scripts/migrate_aseproda_to_odoo.py`: Importador optimizado de clientes y facturas con precarga en memoria y consultas indexadas.
- `scripts/cleanup_aseproda_test_data.py`: Herramienta de purga total para datos de prueba.
- `docs/ACCESO_REMOTO_PISTA_REPSOL_TRIESTE.md`: Documentación exhaustiva de hardware, acceso remoto y despliegue del agente.
- `docs/HISTORICO_PROYECTO_UTRECAR.md`: Histórico técnico completo de cambios y despliegues.
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
