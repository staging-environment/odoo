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

- **E.S. Ronda Norte (Utrera):**
  - **TPV 1 (Puesto Principal con VPN WireGuard):**
    - **IP WireGuard VPN:** `10.8.0.6` (IP Local LAN: `192.168.1.20`)
    - **Usuario Windows:** `jarod` (`desktop-jl2ul2j\jarod`)
    - **Puerto SSH:** `22` (OpenSSH Windows Service)
    - **Acceso directo:** `ssh rondanorte` o `ssh rondanorte-tpv1`
  - **TPV 2 (Puesto Secundario LAN):**
    - **IP Local LAN:** `192.168.1.64`
    - **Usuario Windows:** `madic-tpv` (`madic-tpv-iot\madic-tpv`)
    - **Puerto SSH:** `22` (OpenSSH Windows Service)
    - **Acceso transparente:** `ssh rondanorte-tpv2` (ProxyJump automático a través de TPV 1)
  - **Diagnóstico, Mitigación y Monitorización Centinela en TPVs (Actualizado 06/11/2026):**
    - **Problema diagnosticado:** TPV 2 se congelaba intermitentemente en pantalla táctil al cobrar o atender surtidores.
    - **Acciones Quirúrgicas Aplicadas:**
      1. *Ahorro de energía en NIC Realtek (TPV 2):* Desactivados `*EEE`, `EnableGreenEthernet`, `GigaLite`, `PowerSavingMode` y `AllowComputerToTurnOffDevice: Disabled` (`MSPower_DeviceEnable: False`). Conectividad TCP a `:3306` y `:8777` 100% estable a 1 Gbps.
      2. *Bucle infinito EOVGNET (TPV 1):* Actualizada marca `UltimaSincronizacionConBDCentral = '2021-12-29 17:49:36'` en registro histórico `RRN-2021000001` de `regularizacionesdealmacen`. El bucle de reintentos continuos en `SyncReg.log` ha cesado.
      3. *Reciclaje nocturno de VirtusTPV (TPV 1 y TPV 2 - 04:00 AM):* Tarea programada diaria a las 04:00 AM (`ReciclajeVirtusTPV`). Se corrigió el bug de registro en la ruta (`C:Utrecar...` -> `C:\Utrecar\reciclar_virtustpv.bat`) que provocaba fallo (LastTaskResult = 1), asegurando el reinicio diario limpio y purga de RAM acumulada.
    - **Centinela en Tiempo Real (Instalado 06/11/2026):**
      - Tarea programada `CentinelaTPV2` (`C:\Utrecar\iniciar_centinela.bat` -> `centinela_tpv2.ps1`) ejecutándose 24/7 en TPV 2 como `SYSTEM`.
      - Monitoriza cada 2s la respuesta de GUI (`Responding`), memoria y sockets de red hacia TPV 1 (`:3306` y `:8777`).
      - Envía alertas instantáneas a Telegram (`@utrecar_alertas_bot`) a Jose (`5914920849`) en el momento exacto en que la pantalla se congela, con fotografía forense y aviso de recuperación.
    - **Pendientes para siguiente fase (Actualizado 10/11/2026):**
      - Partición de series fiscales (`TTRN2` / `FTRN2`).
      - Migración de puerto de impresora Epson de WSD a TCP/IP estándar.
      - **Detección de micro-bloqueos al abrir pista de surtidor en TPV 2 (< 5s):**
        - *Hallazgo (10/11/2026):* El Centinela (`PID 14208`) ya corre en `SessionId 1` y el envío a Telegram en JSON UTF-8 hacia el Chat ID exclusivo de José (`5914920849`) funciona correctamente, pero cuando el cajero pulsa en TPV 2 para abrir/autorizar la pista de un surtidor se producen bloqueos de **2 a 4,5 segundos** (observados también en `Actividad.Log` en el hilo principal `[(1)]` durante `FuerzaRecalculoDeOperacionesPendientesDeLiquidar`).
        - *Por qué no saltó la alerta:* La propiedad nativa de Windows `$p.Responding` (`user32.dll!IsHungAppWindow`) tiene un umbral fijo de **5,0 segundos**, por lo que bloqueos de 2 a 4,8 segundos al comunicar con `SDES.exe` (`192.168.1.20:8777` vía `ClienteSDESNet.dll`) o `MySQL` (`3306`) congelan la pulsación del cajero sin que `$p.Responding` cambie a `False`. Además, `Actividad.Log` solo registra liquidaciones/cobros y no las órdenes de apertura de surtidor.
        - *Acción pendiente al retomar:* Inspeccionar los logs de `C:\SDES\*.log` en TPV 1 (`rondanorte`) y de `VirtusTPV Net` en TPV 2, e implementar en `centinela_tpv2.ps1` medición activa de latencia de ventana con `SendMessageTimeout` (`WM_NULL` con umbral de 1.500 ms) y monitorización de latencia de comandos a `SDES` (`:8777`) / `MySQL` (`:3306`), evitando sondeos TCP vacíos que incrementen `Aborted_connects` en MySQL 5.1.
      - **Corrección de IP de VPN en `status.utrecar.com` (`10.8.0.9` ➔ `10.8.0.6`) [COMPLETADO 10/11/2026]:**
        - *Resolución:* Corregida la base de datos MariaDB (`ddev-status-utrecar-db`) y el seeder `StationSeeder.php` en `utrecar-dev`. Se asignaron las IPs reales correctas para todas las estaciones (Ronda Norte `10.8.0.6`, Vistalegre `10.8.0.11`, El Cuervo `10.8.0.9`, Repsol `10.8.0.18`), cesando las falsas alarmas de desconexión de Ronda Norte.
    - **Procedimiento de Reversión / Deshacer (Rollback):**
      - Desactivar Centinela: `ssh rondanorte-tpv2 "schtasks /Change /TN CentinelaTPV2 /Disable && Stop-Process -Name powershell -Force"`
      - Desactivar Reciclaje TPV 1: `ssh rondanorte "schtasks /Change /TN ReciclajeVirtusTPV /Disable"`
      - Desactivar Reciclaje TPV 2: `ssh rondanorte-tpv2 "schtasks /Change /TN ReciclajeVirtusTPV /Disable"`
    - **Alineación con el PRD de Odoo 17 POS:** Este conflicto demuestra la inviabilidad del modelo de base de datos local compartida de Aseproda y valida las especificaciones del PRD de Odoo: sesiones multi-cajero desacopladas (`pos.session`), numeración fiscal particionada por terminal, broker de pista asíncrono vía WebSockets y buffer local offline.
    - **Documentación completa:** `docs/INFORME_TECNICO_DIAGNOSTICO_CONFLICTO_TPVS_RONDA_NORTE.md` e `docs/Informe_Tecnico_Diagnostico_Conflicto_TPVs_Ronda_Norte.pdf`.
---

## ⛽ Arquitectura de Pista y Estrategia de Control (IMPORTANTE)

### 1. Conexión Física y Protocolo Nativo:
- **Sin hardware DOMS:** Las estaciones cuentan con **conexión directa** de los surtidores a los puertos serie / concentrador local en el PC de la estación (`SDES.exe` en `COM3` a 9600 bps).
- **Control MÁSTER en Tiempo Real:** 
  - Odoo POS asume el rol MÁSTER completo sobre la pista.
  - El agente `scripts/agente_pista_odoo_bridge.py` se comunica con el servidor local SDES en `127.0.0.1:8777` usando la librería nativa `ClienteSDESNet.dll` vía `pythonnet`.
  - Permite desbloquear (`Desbloquear(calle)`), bloquear (`Bloquear(calle)`) y cambiar modo de trabajo (`CambiarModoTrabajo(calle, modo)`) de forma inmediata con 0 ms de latencia.
- **Flujo de Control Bidireccional TPV Odoo Cloud ➔ Hardware de Pista:**
  1. **Control de Modo Global y por Calle:**
     - El botón *"PISTA: PREFIJADO / Cambiar a Lleno"* en el TPV o el clic directo en el candado de una calle emite orden vía `/pos_gas_station/set_track_mode`.
     - El agente conmuta en tiempo real el modo en `ModoTrabajo.ini` y en el concentrador SDES (`ClienteSDES2.CambiarModoTrabajo` y `Desbloquear`/`Bloquear`).
  2. **Autorización Directa:**
     - En el frontend de Odoo POS (`extra-addons/pos_gas_station`), el cajero pulsa "AUTORIZAR" o selecciona importe/litros.
     - El controlador `/pos_gas_station/authorize` emite el comando a través de `ir.config_parameter` (`pos_gas_station.pump_command_7`).
     - El agente de pista local captura la orden en milisegundos, invoca `ClienteSDES2.Desbloquear(calle)` y conmuta a `ATENDIDO`.
  3. **Suministro en Pista:**
     - El surtidor físico arranca y despacha el combustible.
  4. **Fin de Suministro y Cobro:**
     - Al colgar la manguera, `dw.log` y MySQL detectan el fin de venta; el agente bloquea la manguera (`Bloquear(calle)` / `PREPAGO`) y traslada la venta al TPV de Odoo en estado "PENDIENTE DE COBRO".
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

## ⚠️ PRINCIPIO ARQUITECTÓNICO CRÍTICO: INDEPENDENCIA TOTAL DE ASEPRODA
- **Objetivo estratégico**: Eliminar completamente cualquier dependencia de software, librerías, bases de datos o archivos propietarios de Aseproda (`VirtusTPV`, `ClienteSDESNet.dll`, `SDES.exe`, `virtusgesnet` MySQL, `dw.log`, `ModoTrabajo.ini`).
- **Desarrollo 100% Propio**: Toda la lógica, drivers, interfaces de comunicación TCP/Serial, protocolos de pista y pantallas de TPV deben ser código nativo propio dentro del repositorio de Odoo (Python, JavaScript OWL y sockets estándar).
- **Transición**: Cualquier protocolo o estructura de datos que se use temporalmente para hablar con el hardware debe ser internalizado mediante drivers nativos en Python puro para que cuando se desinstale Aseproda del equipo de pista, el sistema continúe funcionando de forma autónoma.

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

---

## 🚀 Flujo Obligatorio de Commit, Sincronización Local y Despliegue en Producción
**Regla crítica para cualquier cambio de código en este repositorio:**
- **Si estamos en local (APP de escritorio):** El agente siempre actualiza el entorno local (`git pull origin main` / reinicio de contenedor local si aplica), hace `git commit`, `git push origin main` y despliega automáticamente en producción (`ssh utrecar-dev "cd /home/developer/Projects/odoo && git pull origin main && docker restart ddev-odoo-odoo"`).
- **Si estamos en la nube (`☁️`):** El agente siempre hace `git commit`, `git push origin main` y despliega en producción.
1. `git add <archivos>` y `git commit -m "..."`
2. `git push origin main`
3. Despliegue en servidor Cloud (`utrecar-dev`):
   - `ssh utrecar-dev "cd /home/developer/Projects/odoo && git pull origin main && docker restart ddev-odoo-odoo"`
   - Verificar logs: `ssh utrecar-dev "docker logs --tail 15 ddev-odoo-odoo"`


## 🛡️ Autenticación VPN, Simplificación de Menú y Control de Empleados por Estación (Actualizado)

### 1. Acceso Protegido por VPN y Acceso Administrativo Explícito (?admin=1):
- Cualquier acceso general a `https://odoo.utrecar.com/` muestra por defecto la pantalla de TPV (`select_employee`).
- Si la IP de VPN no pertenece a un puesto de gasolinera (incluidas las IPs de VPN autorizadas para administración: `10.8.0.2`, `10.8.0.3`, `10.8.0.8`, `10.8.0.19`), se muestra la pantalla informativa indicando que el equipo no tiene acceso a TPV de pista, desplegando abajo el enlace **"Acceso administrador"**.
- Al pulsar dicho enlace (o navegar con `?admin=1`), se valida la IP de VPN autorizada y se realiza el auto-login directo como Super Administrador (`jarodriguezbonilla@gmail.com`), accediendo al backend `/web?admin=1`.

### 2. Detección de Estación por IP de WireGuard VPN:
- Los equipos de las gasolineras tienen asignadas IPs fijas en WireGuard:
  - **E.S. Repsol:** `10.8.0.18` (Código Admin Platform: `5`) - **Única estación actualmente con concentrador de pista SDES nativo activo 24/7 en COM3**.
  - **E.S. Ronda Norte:** `10.8.0.6`, `10.8.0.7` (Código Admin Platform: `2`) - *Pendiente de instalación de controladores de hardware*.
  - **E.S. Vistalegre (Utrera):** `10.8.0.11`, `10.8.0.12` (Código Admin Platform: `1`) - *Pendiente de instalación de controladores de hardware*.
  - **E.S. Rodalabota (El Cuervo):** `10.8.0.9`, `10.8.0.10` (Código Admin Platform: `3`) - *Pendiente de instalación de controladores de hardware*.
  - **E.S. Atenas (Écija):** `10.8.0.14`, `10.8.0.15` (Código Admin Platform: `4`) - *Pendiente de instalación de controladores de hardware*.

### 3. Selector Táctil de Empleados desde `admin-platform`:
- Al entrar desde la IP de una gasolinera, Odoo consulta la base de datos de producción de `admin-platform` (`ddev-admin-platform-db`) y despliega la ventana flotante `station_employee_select_modal` con los trabajadores asignados a dicha estación (`gasolinera_codigo`).
- Al pulsar sobre el empleado, se inicia sesión como ese usuario en Odoo, se abre/activa su turno (`pos.session`) y se entra al TPV.
- Cada empleado tiene restringido el acceso únicamente a su estación de servicio asignada.

### 4. Simplificación del Menú Superior:
- Se han eliminado de la barra superior: **Productos**, **Pedidos** e **Informes**.
- Se ha incorporado el nuevo ítem: **"Empleados por Estación (VPN)"** (`action_vpn_station_employees`), que presenta una vista visual interactiva con el resumen de cada gasolinera, sus IPs de VPN, estado del controlador de pista y la tabla completa de empleados asociados desde `admin-platform`.



### 6. Control de Acceso Estricto: TPV Exclusivo por IP de Estación vs Admin
- **Acceso Administrador (IPs VPN generales / oficina)**:
  - Al ingresar a https://odoo.utrecar.com/, auto-login directo como Administrador en /web.
- **Acceso Empleado de Pista (IPs VPN de gasolinera: 10.8.0.18, 10.8.0.6, etc.)**:
  - Al acceder a /, /web o /web/login, queda **estrictamente bloqueado el acceso al backend /web**.
  - Si no hay turno abierto, se presenta la ventana flotante táctil (station_employee_select_modal) solicitando el nombre del empleado (obtenido en tiempo real desde la BD de dmin-platform).
  - Al pulsar sobre su tarjeta de empleado, se autentica su usuario sincronizado en Odoo, se abre su turno (pos.session) y entra **directa y únicamente al TPV** (/pos/ui?config_id=<id>).
  - Cualquier intento de navegar a / o /web desde una IP de estación redirige de forma forzada al TPV de su estación asignada.


### 7. Selector de Estaciones en el TPV y Segregación de Clientes por Estación
- **Botón "Estaciones" en la cabecera del TPV**:
  - Ubicado junto al indicador de estación y botón de cerrar turno (`.btn-topbar-stations`).
  - Al pulsarlo, abre una ventana modal táctil (`stations-selector-modal-window`) que consulta `pos.config.get_user_available_stations()`.
  - Muestra tarjetas con las terminales autorizadas según el usuario y su conexión VPN:
    - **Administrador**: Acceso a todas las estaciones (Repsol, Rodalabota, Vistalegre, Ronda Norte, Atenas) y botón para volver al backend ("Volver a Gestión de Gasolineras").
    - **Operario / Empleado**: Únicamente las estaciones asignadas a su usuario (`pos_config_ids` / estación VPN) y opción de cambiar de cajero.
    - Permite cambiar de terminal (`/pos/ui?config_id=<id>`) con un solo clic.
- **Gestión de Clientes Separada por Estación**:
  - **En el TPV**: `pos.session._loader_params_res_partner()` aplica un dominio estricto `[('station_id', '=', self.config_id.id), ...]`, de modo que cada estación únicamente carga sus clientes asignados (p. ej. los más de 2.200 clientes de Repsol quedan aislados en Repsol y no saturan ni se mezclan con Rodalabota u otras estaciones).
  - **En el Backend (Menú Clientes)**:
    - Vista agrupada por defecto por Estación de Servicio (`'search_default_group_station': 1`).
    - Regla de registro de seguridad (`ir.rule` en `res.partner`): los empleados de pista solo ven clientes asignados a las estaciones a las que tienen permiso, mientras que los administradores conservan acceso global.
    - Creación de clientes desde el TPV o formulario auto-asigna la estación de servicio y compañía correspondiente.


### 8. Seguridad y Acceso SSH Restringido Exclusivamente a Jose por VPN WireGuard
- **Aislamiento a Nivel de Firewall (UFW)**:
  - Puerto 22 (SSH) permitido **únicamente** desde las IPs estáticas de WireGuard asignadas a Jose:
    - `10.8.0.2` (*Jose - Informático*)
    - `10.8.0.19` (*Jose - Informático Salón*)
    - `127.0.0.1` (*Localhost*)
  - El resto de clientes de la VPN (equipos de gasolineras `10.8.0.18`, `10.8.0.6`, etc., y otros empleados) tienen denegado explícitamente el puerto 22 en la interfaz `wg0`.
  - El acceso a SSH desde internet público (IP pública `164.68.101.69`) está completamente cerrado (política Default Deny).
- **Aislamiento a Nivel de Aplicación OpenSSH (`sshd_config.d`)**:
  - Archivo `/etc/ssh/sshd_config.d/allowed_vpn_users.conf`:
    ```sshd
    AllowUsers developer@10.8.0.2 developer@10.8.0.19 developer@127.0.0.1 root@10.8.0.2 root@10.8.0.19 root@127.0.0.1
    ```
- **Configuración de Cliente Local (`~/.ssh/config`)**:
  - `utrecar` y `utrecar-dev` apuntan directamente a `Hostname 10.8.0.1` a través de la VPN WireGuard.


### 9. Integración con admin-platform: Enlace en Menú Principal y Permiso acceso_odoo
- **Acceso a Odoo en el Menú Principal (`utrecar.com/admin`)**:
  - En `resources/views/layouts/navigation.blade.php`, se ha añadido un botón/enlace directo hacia `https://odoo.utrecar.com` (en modo desktop y móvil/responsive).
  - Condicionado mediante `@if(auth()->user()?->can('acceso_odoo'))`.
- **Nuevo Permiso en la Matriz de Permisos (`admin-platform`)**:
  - Permiso Spatie creado en base de datos: `acceso_odoo` (guard `web`).
  - Agregado en `resources/views/filament/pages/permission-matrix.blade.php` bajo la sección *Gasolineras*:
    `'acceso_odoo' => 'Acceso a Odoo (ERP / TPV)'`.
  - Permite a los administradores activar o revocar en tiempo real el acceso a Odoo para cualquier rol (`CEO`, `ADMINISTRACION Y RRHH`, `Empleado`) o usuario individual.
- **Validación del Permiso en el TPV de Odoo**:
  - En `pos_config.get_admin_platform_employees()`, la consulta a la tabla `empleados` cruza con `users`, `model_has_roles`, `role_has_permissions` y `model_has_permissions` de MariaDB para verificar que el empleado cuenta con el permiso `acceso_odoo`. Si el permiso está desactivado para su rol o usuario, no aparecerá en el selector táctil de la estación ni podrá abrir turno.


### 10. Hoja de Ruta: Ubicaciones de Trabajo Múltiples por Empleado (Admin Platform & Odoo)
- **Requisito Fundamental de Operativa**:
  - En la base de datos de `admin-platform`, la **Ubicación de trabajo de un empleado debe ser múltiple** (muchos a muchos N:M), ya que los expendedores y encargados cubren turnos de forma rotativa en varias estaciones de servicio (p. ej. Vistalegre y Ronda Norte, o Repsol y Rodalabota).
- **Implementación Técnica Prevista en `admin-platform` (MariaDB)**:
  - Crear tabla relacional `empleado_gasolinera` (`empleado_id`, `gasolinera_codigo`) o columna JSON/string con la lista de códigos asignados (`gasolinera_codigos = [1, 2, 5]`).
- **Regla de Visualización Estricta al Abrir Turno en Odoo**:
  - Al abrir turno en cualquier terminal táctil (`/pos_gas_station/select_employee?station_id=<id>`), **únicamente deben salir los empleados que tengan asignada esa ubicación de trabajo específica**.
  - Si un empleado tiene asignadas múltiples estaciones, su tarjeta aparecerá en el selector de cada una de esas terminales.
  - Al hacer clic sobre su nombre, se le abre el turno (`pos.session`) y se vincula su usuario de Odoo (`res.users`), asociando todas sus ventas, cobros y arqueos a esa sesión de caja específica.
- **Sincronización Automática con `res.users`**:
  - En Odoo, el usuario se vincula a todas las estaciones en `pos_config_ids` y se añade a `pos.config.allowed_user_ids` de cada terminal respectiva.
- **Documentación de Detalle**: Consultar `docs/ARQUITECTURA_UBICACIONES_MULTIPLES_EMPLEADOS.md`.

---

## 👥 Sistema de Permisos y Asignación Multi-Rol por Empresa

### 1. Modelo de Datos Multi-Rol
- **`res.users`**:
  - `utrecar_role_ids`: Many2many con `utrecar.role`. Almacena todos los roles activos del usuario.
  - `utrecar_role_id`: Many2one compute/inverse al rol principal (primer rol asignado).
  - `company_access_ids`: One2many con `utrecar.employee.company.access`.
- **`utrecar.employee.company.access`**:
  - `role_ids`: Many2many con `utrecar.role` (tabla relacional `utrecar_emp_comp_role_rel`). Permite múltiples roles para una misma empresa (ej. EMPLEADO + GESTOR en A.R. Trieste).
  - `role_id`: Many2one compute/inverse al rol principal de la empresa.
  - `active_access`: Boolean switch que habilita o deshabilita el acceso del empleado a dicha empresa.
- **Métodos Clave**:
  - `user.get_company_roles(company_id)`: Devuelve el recordset de todos los roles activos del usuario en esa empresa.
  - `user.is_employee_for_company(company_id)`: Verifica si el usuario tiene asignado el rol EMPLEADO en la empresa consultada para autorizar su aparición en el selector de turnos táctil del TPV.
  - `user.has_utrecar_permission(perm_code, company_id)`: Evalúa permisos considerando la configuración aislada por empresa (`utrecar.company.role.permission`) de cualquiera de los roles que el usuario posea.

### 2. Pantalla "Personal, Empresas y Roles"
- Componente OWL: `EmployeeCompanyRolesView` (`extra-addons/pos_gas_station/static/src/js/employee_company_roles.js` y `employee_company_roles.xml`).
- Casillas interactivas con dropdown flotante multi-selección (`role-dropdown-popover`) para A.R. Trieste (ID 4) y Utrecar S.L. (ID 1).
- Los badges se renderizan dinámicamente con sus colores correspondientes (`#0284c7`, etc.) reflejando de inmediato los roles asignados.


### 11. Gestión de Sobrantes de Prepago Incompleto, Monedita en Surtidor y Optimización del Historial de Turno (10/11/2026)

#### A. Optimización del Historial de Turno y Anulación de Tickets:
- **Maquetación compacta a una sola fila por ticket**:
  - Eliminadas las columnas redundantes `ESTADO` y `FACTURA` de la tabla de turnos (`shift-orders-table`).
  - Anchos de columna fijos ajustados: `FECHA` (135px), `Nº TICKET` (85px), `RECIBO` (155px), `CLIENTE` (180px con `text-overflow: ellipsis`), `CAJERO` (130px), `TOTAL` (80px), `ACCIONES` (220px).
  - Ventana flotante ampliada a `1040px` con `overflow-x: hidden`, eliminando por completo el scroll horizontal.
- **Identificación visual de tickets anulados**:
  - Fondo en rojo pastel suave (`background-color: #fee2e2 !important; color: #991b1b !important; border-left: 5px solid #dc2626 !important;`).
  - Columna de ticket compactada mostrando tooltip explicativo (`title="Ticket Anulado [TTTR_xxxx]"`).
- **Corrección de ventana emergente de confirmación de anulación**:
  - Clase `.annul-order-modal-backdrop` con `z-index: 10800 !important;` y `.utrecar-annul-confirm-modal` con `z-index: 10801 !important;`, garantizando que el modal de confirmación se muestre por encima del historial (`z-index: 10500`) y no quede oculto detrás.

#### B. Gestión de Sobrantes de Prepago Incompleto (Puntos 9 y 10):
- **Detección Automática de Sobrante**:
  - Al validar un prepago en el TPV, los datos de la orden (`amount`, `liters`, `fuel`, `productId`, `unitPrice`, `orderRef`, `partner`, `isMoney`) se almacenan de forma persistente en `pos.pumpPresets` (`localStorage`).
  - Durante el suministro, `fetchPumpsStatus()` rastrea `maxDispensedAmount` y `maxDispensedLiters`.
  - Cuando el cliente cuelga la manguera habiendo repostado menos de lo prefijado (ej. pagó 20€/20L y sólo echó 15€/15L, diferencia > 0.05€):
    - Se genera automáticamente una operación en `pos.pendingSales[pump.id]` con `isPrepayRefund: true`, `refundAmount: -diffAmt` y `refundLiters: -diffLts` en **negativo**.
    - Se limpia el preset y se libera la calle en pista vía `/pos_gas_station/clear_pump`.
- **Prioridad Visual Amarilla del Surtidor (`.has-uncollected-coin`)**:
  - Siempre que un surtidor tenga moneditas pendientes (tanto por modo lleno postpago como por sobrante de prepago), la caja del surtidor permanece en **AMARILLO** (`border: 3px solid #ca8a04`, `background: #fefce8`, `corner-tab: #eab308` y cuerpo inferior `#eab308` con dial lock), **incluso si la pista se cierra o se conmuta a modo prepago/bloqueado**.
- **Ventana Flotante de la Monedita para Sobrantes**:
  - Al pulsar la monedita (o hacer clic en la tarjeta del surtidor), se muestra la tarjeta con la insignia `⚠️ SOBRANTE DE PREPAGO`.
  - Muestra el detalle de `Prefijado` vs `Repostado en pista` y resalta en tamaño grande y color rojo el importe exacto pendiente:
    `FALTA POR ECHARSE (A DEVOLVER): -X.XX € (-X.XX L)`.
  - Botonera exclusiva con las 4 acciones permitidas (Punto 10):
    1. 🖨️ **Hacer Ticket**: Prepara el ticket simplificado de devolución del sobrante en negativo.
    2. 📋 **Hacer Albarán**: Genera el abono en albarán de crédito si es cliente de cuenta.
    3. 📄 **Hacer Factura**: Emite factura rectificativa a cliente con CIF/NIF.
    4. 💾 **Guardar sin ticket**: Mantiene la operación aparcada en la monedita sin emitir documento.
- **Composición del Ticket (Punto 2)**:
  - 1 sola línea de combustible con la cantidad en **negativo** (`-diffLts`) e importe neto ajustado para que el total con impuestos sea exactamente el importe en **negativo** (`-diffAmt`, ej: `-5,00 €`).
  - Concepto en la línea: *`Calle X - Sobrante de Prefijado [Prefijado: 20.00 L | Repostado: 15.00 L]`*.
  - Total del ticket en negativo: `-5,00 €`.
  - Método `ensureOrderPaid()` en `PaymentScreen` adaptado (`Math.abs(due) > 0.001`) para permitir la cobertura y validación directa de tickets con importe negativo en efectivo o tarjeta.
- **Sincronización con el Hardware / Agente de Pista (`agente_pista_odoo_bridge.py`)**:
  - Modificado `marcar_calle_completada`: cuando `importe < (preset_amount - 0.05)`, el puente en Repsol (`10.8.0.18`) no limpia la calle ni pone importe a cero; bloquea la manguera y conserva `status = "ready"` y `statusText = "SOBRANTE X.XX€"`, manteniendo el saldo reportado a Odoo hasta su resolución desde el TPV.
