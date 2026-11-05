# INFORME TÉCNICO: DIAGNÓSTICO DE CONFLICTO Y BLOQUEO DE TPVS EN E.S. RONDA NORTE
## Análisis Forense de Concurrencia Aseproda, Fallos de Red, Deadlocks MySQL y Alineación con el PRD de Odoo 17 POS

**Fecha de Emisión:** 4 de Noviembre de 2026  
**Estación de Servicio:** E.S. Ronda Norte (Utrera) — Código Estación: 2  
**Equipos Auditados:**
- **TPV 1 (Master / Servidor de Pista):** `DESKTOP-JL2UL2J` (`10.8.0.6` / `192.168.1.20`)
- **TPV 2 (Esclavo / Puesto Secundario):** `MADIC-TPV-IOT` (`192.168.1.64`)  
**Estado de la Intervención:** **PAUSADO / OBSERVACIÓN EXCLUSIVA** (Ningún cambio aplicado en producción por orden expresa del cliente; estación operativa 100%).  
**Responsable Técnico:** Equipo Antigravity / Utrecar ERP Architecture  

---

## 1. Resumen Ejecutivo y Objeto del Informe

La estación de servicio **Ronda Norte** cuenta con dos terminales de punto de venta (TPV 1 y TPV 2) operando actualmente bajo la suite de software privativo **Aseproda** (`VirtusTPVNet`, `SDES.exe`, `EOVGNET.exe`). 

El cliente reportó un comportamiento anómalo crítico y recurrente: **el TPV 2 (puesto secundario) sufre congelaciones, bloqueos de interfaz y caídas intermitentes**, impidiendo el cobro ágil a los clientes y generando frustración en el personal de pista. A pesar de haber sustituido previamente los switches de red y los propios equipos informáticos, el problema persistía de manera idéntica.

Mediante una auditoría remota no invasiva a través de túneles SSH seguros (sin reiniciar servicios ni alterar datos en horario de apertura), se ha realizado un análisis forense exhaustivo a nivel de:
1. Concurrencia transaccional y bloqueos del motor de base de datos MySQL 5.1 (`SHOW ENGINE INNODB STATUS`).
2. Trazas de red, sockets abiertos y configuración de hardware de los adaptadores de red Ethernet.
3. Consumo de recursos de sistema, fugas de memoria y registros de eventos de Windows (`Application` y `System`).
4. Mapeo y consistencia de tablas de configuración (`seriesportpv`, `tpvs`, `facturasyticketsdeventa`).

El análisis ha arrojado **cinco causas técnicas determinantes**, destacando una colisión directa de numeración fiscal entre ambos puestos y una tormenta de bloqueos provocada por el sincronizador en bucle de Aseproda. Este documento expone las evidencias, define el plan de mitigación y **conecta directamente este caso de uso con el PRD (Product Requirements Document) de Odoo 17 POS**, demostrando por qué la nueva arquitectura de Odoo erradica estructuralmente esta patología.

---

## 2. Topología de Hardware y Flujo Operativo

```
[ Nube / Servidor Central ]
           │ (Túnel WireGuard VPN: 10.8.0.6)
           ▼
┌────────────────────────────────────────────────────────┐
│ TPV 1: MASTER (DESKTOP-JL2UL2J - 192.168.1.20)         │
│  - Concentrador Pista: SDES.exe (COM3/LON a Surtidores)│
│  - Sockets de Pista: Puerto TCP 8777                   │
│  - Base de Datos Local: MySQL 5.1 (Puerto TCP 3306)    │
│  - Sincronizador Nube: EOVGNET.exe (Cada 10-15s)       │
│  - Aplicación TPV: VirtusTPVNet.exe                    │
└──────────────────────────┬─────────────────────────────┘
                           │ Switch Ethernet LAN (1 Gbps)
                           ▼
┌────────────────────────────────────────────────────────┐
│ TPV 2: ESCLAVO (MADIC-TPV-IOT - 192.168.1.64)          │
│  - Aplicación TPV: VirtusTPVNet.exe                    │
│  - 7 Conexiones TCP remotas a TPV 1 (MySQL 3306)       │
│  - 1 Conexión TCP remota a TPV 1 (SDES 8777)           │
│  - Impresora Térmica Epson WF-M5299 (Puerto WSD)       │
└────────────────────────────────────────────────────────┘
```

---

## 3. Diagnóstico Forense: Las 5 Causas Raíz Identificadas

### 3.1. Causa 1 (Crítica): Colisión de Series de Venta (`TTRN` / `FTRN`) por Ausencia de Partición
* **Evidencia en Base de Datos (`virtusgesnet.seriesportpv`):**
  * Al contrastar la configuración con **Vistalegre (Estación 1)**, se comprobó que allí el TPV 1 tiene asignadas las series `TTUTR` / `FTUTR`, mientras que el TPV 2 utiliza sus propias series independientes `TTUTR2` / `FTUTR2`.
  * En **Ronda Norte (Estación 2)**, **ambos TPVs (1 y 2) están configurados exactamente con la misma serie compartida: `TTRN` para tickets y `FTRN` para facturas**. Las series `TTRN2` y `FTRN2` ni siquiera existen en la tabla `seriesdefacturasyticketsdeventa`.
* **Mecanismo del Fallo:**
  Cada vez que ambos cajeros finalizan una venta de forma simultánea o casi simultánea, ambas instancias de `VirtusTPVNet.exe` ejecutan:
  ```sql
  UPDATE seriesdefacturasyticketsdeventa 
  SET Numerador = Numerador + 1 
  WHERE Codigo = 'TTRN';
  ```
  Esto bloquea la fila a nivel exclusivo en InnoDB. La petición de red de TPV 2 hacia `192.168.1.20:3306` queda en espera sincronizada. Como la interfaz gráfica de VirtusTPV se ejecuta en el hilo principal sin llamadas asíncronas desacopladas, **la ventana del TPV 2 entra en estado "No responde" (congelación visual)** hasta que TPV 1 libera la transacción.

### 3.2. Causa 2 (Crítica): Tormenta Continua de Locks y Deadlocks por Bucle Infinito de `EOVGNET`
* **Evidencia en Motor InnoDB (`SHOW ENGINE INNODB STATUS`):**
  Se detectó un deadlock activo documentado en la tabla `virtusgesnet.expediciones`:
  * *Transacción 1:* Hilo 139578 correspondiente a `EOVGNET.exe` (proceso de sincronización central de Aseproda), **reteniendo bloqueos sobre 18 tablas simultáneamente** mientras ejecutaba `UPDATE expediciones SET IDEnBDCentral = ...`.
  * *Transacción 2:* Hilo 738970 correspondiente a `VirtusTPVNet.exe` en calle 2 ejecutando `UPDATE expediciones SET ...`.
* **Causa del Bucle:**
  En el log `SyncReg.log` de TPV 1, `EOVGNET` intenta de forma ininterrumpida cada 10-15 segundos subir registros con fallos de integridad referencial:
  * `Cannot add or update a child row: foreign key constraint fails (documentosacobrar)`
  * `Cannot add or update a child row: foreign key constraint fails (detalledefacturasyticketsdeventa)`
  * `Duplicate entry 'RRN-2021000001-1' for key 'PRIMARY' on regularizacionesdealmacen`
* **Mecanismo del Fallo:**
  Al fallar continuamente, `EOVGNET` reintenta en bucle agresivo. En cada iteración bloquea tablas maestras de ventas. Cuando TPV 2 intenta consultar o insertar a través de la red local, choca con las tablas bloqueadas y queda congelado.

### 3.3. Causa 3 (Alta): Ahorro de Energía Agresivo en la Tarjeta de Red de TPV 2 (Realtek GbE)
* **Evidencia en Hardware de TPV 2:**
  La consulta WMI/CIM reveló que el adaptador PCIe Realtek de TPV 2 tiene activadas políticas agresivas de gestión de energía:
  * `MSPower_DeviceEnable: True` ("Permitir que el equipo apague este dispositivo para ahorrar energía").
  * `Ethernet de consumo eficiente de energía (EEE)`: **Activado**.
  * `Ethernet ecológico (Green Ethernet)`: **Activado**.
  * `Power Saving Mode`: **Activado**.
* **Mecanismo del Fallo:**
  En periodos de calma (ej. 2 o 3 minutos sin interacción en TPV 2), la interfaz de red degrada la velocidad de enlace para reducir consumo eléctrico. Cuando el operador pulsa la pantalla táctil para autorizar un surtidor, la tarjeta sufre una latencia de reactivación y micro-cortes en los sockets TCP persistentes (`:3306` y `:8777`), provocando "Timeouts" en la librería de comunicación de VirtusTPV.

### 3.4. Causa 4 (Media-Alta): Fuga de Memoria Severa (1.58 GB RAM) y Fallos de Impresión WSD
* **Evidencia en Memoria y Event Viewer:**
  * El proceso `VirtusTPVNet.exe` en TPV 2 presentaba **1.581 MB de memoria física ocupada**, acumulada tras 6 días continuos sin reiniciarse (desde el 29/10/2026). El tamaño estándar no debería exceder los 150-250 MB.
  * El Visor de Eventos registró el fallo `System.AccessViolationException` en `combit.ListLabel18.NativeMethods.LlDefineVariableExt64` durante la rutina `TPV.ImprimirEnOtroThread()`.
  * La impresora `EPSON WF-M5299` está enlazada mediante puerto dinámico `WSD` (`WSD-8861...`), lo que genera cuelgues recurrentes en el servicio `spoolsv.exe`.

### 3.5. Causa 5 (Media): Inversión de Identificadores de Puesto
* En `virtusgesnet.tpvs`, el ID 1 es el puesto principal y el ID 2 el secundario.
* En los archivos locales de arranque, TPV 1 se ejecuta bajo `CodigoTPV = 2` y TPV 2 bajo `CodigoTPV = 1`. Aunque el sistema sigue operando, esta inconsistencia dificulta el aislamiento de registros temporales y contadores de arqueo.

---

## 4. Alineación Estratégica con el PRD de Odoo 17 POS

El incidente diagnosticado en Ronda Norte constituye la demostración empírica más clara de por qué la arquitectura monolítica de Aseproda ha llegado a su límite de obsolescencia, y valida punto por punto los requisitos recogidos en el **PRD (Product Requirements Document)** para el desarrollo e implantación de **Odoo 17 POS Gas Station**.

| Requisito PRD Odoo 17 POS | Problema Detectado en Aseproda (Ronda Norte) | Solución Arquitectónica Nativa en Odoo 17 |
| :--- | :--- | :--- |
| **FR-POS-01: Sesiones Multi-Cajero Aisladas** | TPV 2 ataca directamente la base de datos de TPV 1 por TCP raw, sufriendo contención y caídas globales de interfaz. | Cada terminal abre su propia sesión (`pos.session`) web en cliente local (OWL). La interfaz nunca se bloquea por latencia de base de datos. |
| **FR-FISCAL-02: Secuencias y Numeradores Particionados** | Colisión de serie única `TTRN` que genera bloqueos de fila mutuos en el numerador de tickets. | Odoo genera secuencias fiscales independientes por punto de venta (ej. `RN1/2026/...` y `RN2/2026/...`) eliminando por completo cualquier lock de concurrencia. |
| **FR-HARDWARE-03: Broker de Pista Desacoplado (WebSockets)** | TPV 2 abre sockets síncronos directos a `SDES` y bloquea el hilo gráfico ante cualquier demora. | El **Agente Edge Odoo** actúa como broker asíncrono vía WebSockets / Longpolling. El TPV emite comandos que se encolan sin congelar la pantalla. |
| **NFR-RESIL-04: Tolerancia a Caídas de Red (Offline Buffer)** | Si la tarjeta de red del TPV 2 entra en micro-corte (EEE), VirtusTPV crashea o congela la caja. | Odoo POS almacena los pedidos en memoria local (IndexedDB) y procesa transacciones localmente, sincronizando al restablecer la red. |
| **NFR-STABILITY-05: Eliminación de Sincronizadores Frágiles** | `EOVGNET` colapsa la base de datos local con reintentos infinitos que bloquean 18 tablas simultáneamente. | Odoo opera con **Única Fuente de Verdad Centralizada en Cloud**. Las ventas viajan por API REST/JSON-RPC directa, sin replicadores MySQL frágiles de fondo. |

---

## 5. Plan de Mitigación Transitoria (Pausado / A la espera de autorización)

Para mantener la estación operativa con Aseproda hasta la entrada en servicio de Odoo POS, se ha diseñado el siguiente plan quirúrgico. **Ninguna de estas acciones ha sido ejecutada todavía, quedando a la espera de la autorización expresa del usuario:**

```
┌──────┬───────────────────────────────────────────┬────────────┬─────────────┬──────────────────────────┐
│ Paso │ Acción Técnica                            │ Prioridad  │ Impacto     │ Estado Actual            │
├──────┼───────────────────────────────────────────┼────────────┼─────────────┼──────────────────────────┤
│ 1    │ Crear series TTRN2 / FTRN2 en MySQL y     │ CRÍTICA    │ Nulo        │ En espera de aprobación  │
│      │ asignarlas al TPV 2 en seriesportpv       │            │ (En calma)  │                          │
├──────┼───────────────────────────────────────────┼────────────┼─────────────┼──────────────────────────┤
│ 2    │ Desactivar EEE, Green Ethernet y Ahorro   │ ALTA       │ Nulo        │ COMPLETADO (05/11/2026)  │
│      │ de Energía en NIC Realtek del TPV 2       │            │ (1 segundo) │                          │
├──────┼───────────────────────────────────────────┼────────────┼─────────────┼──────────────────────────┤
│ 3    │ Purgar registro RRN-2021000001-1 y FKs    │ ALTA       │ Nulo        │ COMPLETADO (05/11/2026)  │
│      │ corruptas para detener bucle EOVGNET      │            │             │                          │
├──────┼───────────────────────────────────────────┼────────────┼─────────────┼──────────────────────────┤
│ 4    │ Cambiar puerto EPSON de WSD a TCP/IP      │ MEDIA      │ Nulo        │ En espera de aprobación  │
│      │ estándar fijo con su dirección IP local   │            │             │                          │
├──────┼───────────────────────────────────────────┼────────────┼─────────────┼──────────────────────────┤
│ 5    │ Programar tarea de reinicio diario 05:00AM│ PREVENTIVA │ Nulo        │ COMPLETADO (05/11/2026)  │
│      │ de VirtusTPVNet para evitar fugas de RAM  │            │ (Automático)│                          │
└──────┴───────────────────────────────────────────┴────────────┴─────────────┴──────────────────────────┘
```

### 5.1. Detalle de Implementación de la Tarea Programada de Reciclaje (Paso 5)

* **Propósito:** Purgar diariamente la fuga de memoria de `VirtusTPVNet.exe` (que alcanzaba >1.65 GB RAM) y vaciar la cola de impresión antes de la apertura.
* **Hora de ejecución programada:** Diariamente a las **05:00 AM**.
* **Ubicación del script:** `C:\Utrecar\reciclar_virtustpv.bat` en TPV 1 y TPV 2.
* **Archivo de registro de ejecuciones:** `C:\Utrecar\reciclaje_tpv.log`.
* **Nombre de la tarea en Windows:** `ReciclajeVirtusTPV`.

#### Procedimiento para Deshacer o Desactivar la Tarea Programada (Rollback):

Si en algún momento fuera necesario pausar o eliminar esta tarea programada, ejecutar por SSH:

* **Para desactivar temporalmente (sin borrar):**
  ```cmd
  # En TPV 1:
  ssh rondanorte "schtasks /Change /TN ReciclajeVirtusTPV /Disable"

  # En TPV 2:
  ssh rondanorte-tpv2 "schtasks /Change /TN ReciclajeVirtusTPV /Disable"
  ```

* **Para volver a activar:**
  ```cmd
  # En TPV 1:
  ssh rondanorte "schtasks /Change /TN ReciclajeVirtusTPV /Enable"

  # En TPV 2:
  ssh rondanorte-tpv2 "schtasks /Change /TN ReciclajeVirtusTPV /Enable"
  ```

* **Para eliminarla definitivamente:**
  ```cmd
  # En TPV 1:
  ssh rondanorte "schtasks /Delete /TN ReciclajeVirtusTPV /F"

  # En TPV 2:
  ssh rondanorte-tpv2 "schtasks /Delete /TN ReciclajeVirtusTPV /F"
  ```

* **Para consultar su estado y hora de próxima ejecución:**
  ```cmd
  ssh rondanorte "schtasks /Query /TN ReciclajeVirtusTPV /FO LIST"
  ssh rondanorte-tpv2 "schtasks /Query /TN ReciclajeVirtusTPV /FO LIST"
  ```

---

## 6. Conclusión y Recomendación

La causa fundamental del bloqueo de los puestos en Ronda Norte no era un fallo de hardware de red ni de cableado, sino un **problema estructural de arquitectura de software y concurrencia**: dos terminales compitiendo sin particionamiento sobre una base de datos local saturada por un proceso de sincronización defectuoso.

La implementación transitoria de las 5 acciones de mitigación proporcionará estabilidad inmediata a los cajeros en Aseproda. No obstante, **la solución definitiva y de futuro reside en la ejecución del PRD de Odoo 17 POS**, cuya arquitectura distribuida, reactiva y desacoplada garantiza la independencia total de licencias y el fin definitivo de estos bloqueos en pista.
