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

## 🚀 Flujo Obligatorio de Commit y Despliegue en Producción
**Regla crítica para cualquier cambio de código en este repositorio:**
Cada vez que se realice un cambio, fix o nueva funcionalidad, el agente **siempre debe commitear, hacer push a `origin/main` y desplegar automáticamente en producción**:
1. `git add <archivos>` y `git commit -m "..."`
2. `git push origin main`
3. Despliegue en servidor Cloud:
   - `ssh utrecar-dev "cd /home/developer/Projects/odoo && git pull origin main && docker restart ddev-odoo-odoo"`
   - Verificar logs: `ssh utrecar-dev "docker logs --tail 15 ddev-odoo-odoo"`


## 🛡️ Autenticación VPN, Simplificación de Menú y Control de Empleados por Estación (Actualizado)

### 1. Acceso Protegido por VPN y Auto-login Administrador:
- Al estar el servidor de producción protegido por WireGuard VPN interna, cualquier acceso a `https://odoo.utrecar.com/` desde IPs que no son puestos de gasolinera entra directamente autenticado con el usuario Administrador (`jarodriguezbonilla@gmail.com`).
- Se mantiene el bypass manual con `?admin=1` para acceso administrativo explícito.

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
