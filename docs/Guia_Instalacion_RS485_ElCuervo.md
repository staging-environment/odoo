# UTRECAR ERP - Guía Técnica de Instalación RS485 & Odoo Cloud (E.S. Rodalabota - El Cuervo)

## 📌 Resumen General
Esta documentación detalla el proceso de digitalización e integración en tiempo real entre el hardware de pista Aseproda de la estación de servicio **E.S. Rodalabota (El Cuervo)** y la plataforma en la nube **Odoo Cloud (`https://odoo.utrecar.com`)**.

---

## 📦 0. Instalación Previa Obligatoria de Software (Desde Cero)
Antes de ejecutar cualquiera de los scripts en el PC de la gasolinera:

1. **Instalación de Python 3.12:**
   - **Opción Con Internet:** Ejecutar en PowerShell:
     ```powershell
     winget install Python.Python.3.12 --override "/passive InstallAllUsers=1 PrependPath=1"
     ```
   - **Opción Sin Internet (Pendrive):** Descargar `python-3.12.x-amd64.exe` desde `https://www.python.org/downloads/`. Al instalar, **MARCAR OBLIGATORIAMENTE:** `☑ Add python.exe to PATH`.

2. **Driver FTDI para Conversor DSD TECH SH-U10:**
   - Enchufar el USB DSD TECH. Si aparece exclamación en Administrador de Dispositivos, instalar `CDM21236_Setup.exe` desde la web oficial de FTDI.

3. **Librerías de Comunicación Python:**
   - Ejecutar en PowerShell: `pip install pyserial requests`
   - *(O bien ejecutar `install_prerequisites.ps1`)*.

---

## 🔌 1. Esquema de Empalme Eléctrico en Pista (Puente RS485)

### Cajita Metálica Verde Aseproda (Existente)
- **Ranura 1 (Negro):** RS485 `Data+ (A)`
- **Ranura 2 (Blanco):** RS485 `Data- (B)`
- **Ranuras 3 a 6:** VACÍAS

### Conexión del Conversor DSD TECH SH-U10
- **Hilo 1** (Empalmar en Ranura 1 junto al negro) ➔ Terminal **`A+`** en DSD TECH
- **Hilo 2** (Empalmar en Ranura 2 junto al blanco) ➔ Terminal **`B-`** en DSD TECH
- **`GND` y `5V0`:** VACÍOS
- **USB:** Enchufar al PC de caja

---

## ⚡ 2. Protocolo de Ejecución Secuencial en PowerShell (Orden 1 a 4)

| Orden | Archivo en `docs/` | Propósito | Comando Exacto en PowerShell |
| :---: | :--- | :--- | :--- |
| **ORDEN 1** | **`install_prerequisites.ps1`** | Instala Python 3.12, PySerial y Requests en 1 clic. | `powershell -ExecutionPolicy Bypass -File .\install_prerequisites.ps1` |
| **ORDEN 2** | *(Acción Física)* | Empalme de Hilo 1 $\rightarrow$ `A+` e Hilo 2 $\rightarrow$ `B-`. | *(Atornillar bornes y enchufar USB)* |
| **ORDEN 3** | **`test_rs485.py`** | Prueba en directo con Auto-Detección de puerto COM. | `python test_rs485.py` |
| **ORDEN 4** | **`start_daemon.ps1`** | Arranca `agente_odoo_elcuervo.py` en segundo plano. | `powershell -ExecutionPolicy Bypass -File .\start_daemon.ps1` |

---

## ⏱️ 3. Cronograma de Señales de Surtidores en Consola

1. **Reposo (Idle):** Polling constante de Aseproda cada 0.5s-1s (`02 30 31 41 43...`).
2. **Descolgar Manguera:** Aviso inmediato de manguera levantada (`02 30 31 53 54...`).
3. **Repostaje en Vivo:** Conteo progresivo de litros en tiempo real (`02 30 31 44 41...`).
4. **Colgar Manguera:** Totalización final de litros e importe (`02 30 31 45 4E 44...`). En este segundo exacto se envía el manguerazo a Odoo Cloud.

---

## 🌐 4. Sincronización Automática con Odoo Cloud (`https://odoo.utrecar.com`)

El script `agente_odoo_elcuervo.py` utiliza la API XML-RPC nativa de Odoo con las credenciales de la estación:
- **URL:** `https://odoo.utrecar.com`
- **DB:** `odoo`
- **Usuario:** `jarodriguezbonilla@gmail.com`
- **Contraseña:** `Utrecar2026!`

Al colgar la manguera, el suministro aparece automáticamente en el TPV de **E.S. Rodalabota (El Cuervo)** listo para cobrar y descontar del tanque de inventario.
