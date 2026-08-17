# UTRECAR ERP — Integración Aseproda & Odoo Cloud (E.S. Rodalabota - El Cuervo)
## 🔌 Manual Técnico de Despliegue: Splitter COM y Ejecución de Scripts (1 Solo Cable)

---

### 📌 Resumen Operativo (Sin Modificar Cableado)
La caja negra de Aseproda permanece conectada por su único cable USB al TPV principal. Mediante el **Splitter Virtual VSPE**, clonamos su puerto serie físico en el puerto virtual **COM10**. A continuación, ejecutamos la secuencia de scripts de la carpeta `scripts/` (u orden 1 a 5) para que el TPV de caja y Odoo Cloud convivan al 100% de forma simultánea.

---

### 🗺️ 1. Tabla Maestra de Scripts y Secuencia de Ejecución (Orden 1 a 5)

| Orden | Archivo Script | Propósito | Comando Exacto en PowerShell |
| :---: | :--- | :--- | :--- |
| **PASO 1** | **`install_prerequisites.ps1`** | Instala Python 3.12, pip, pyserial y requests en 1 solo clic. | `powershell -ExecutionPolicy Bypass -File .\install_prerequisites.ps1` |
| **PASO 2** | *(Software VSPE)* | Crea el Splitter Virtual que une el COM real de Aseproda con **COM10**. | *(Crear Splitter en interfaz VSPE y guardar `vspe_config.vspe`)* |
| **PASO 3** | **`test_rs485.py`** | Prueba interactiva en vivo para comprobar que entran tramas por **COM10**. | `python test_rs485.py` |
| **PASO 4** | **`start_daemon.ps1`** | Inicia `agente_odoo_elcuervo.py` en segundo plano invisible ahora mismo. | `powershell -ExecutionPolicy Bypass -File .\start_daemon.ps1` |
| **PASO 5** | **`setup_task_scheduler.ps1`** | Registra la Tarea Programada de Windows para persistencia 24/7 tras reinicios. | `powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1` |

---

### 🏗️ 2. Esquema de Arquitectura por Software (1 Solo Cable)

```
[Surtidores Pista] ==(Cable 2 Hilos RS-485)==> [Caja Negra Aseproda] ==(1 Cable USB)==> [COM3 Físico en TPV]
                                                                                               │
                                                                                               ▼
                                                                                   [VSPE / Splitter Virtual]
                                                                                         ┌─────┴─────┐
                                                                                         ▼           ▼
                                                                                [Virtual COM10] [Virtual COM10]
                                                                                       │           │
                                                                                       ▼           ▼
                                                                                [TPV Aseproda] [Agente Odoo Cloud]
                                                                                (Cobra/Tickets) (Sube a Odoo Web)
```

---

### 🚀 3. Detalle de Ejecución Fase por Fase

#### FASE 1: Instalación de Prerrequisitos en Windows
Abre una consola de **PowerShell como Administrador** en el TPV principal y ejecuta:
```powershell
powershell -ExecutionPolicy Bypass -File .\install_prerequisites.ps1
```
*Efecto:* Descarga e instala automáticamente Python 3.12 y las librerías `pyserial` y `requests`.

---

#### FASE 2: Configuración de VSPE (Splitter COM3 ➔ COM10)
1. **Identificar puerto COM real:** Pulsa `Win + X` ➔ *Administrador de Dispositivos* ➔ *Puertos (COM y LPT)*. Desconecta y reconecta el USB de la caja Aseproda para ver qué puerto reaparece (ejemplo: `COM3`).
2. **Crear Splitter en VSPE:**
   - Abre **VSPE** como Administrador ➔ Menú **Device ➔ Create...** ➔ Selecciona **Splitter** ➔ *Next*.
   - **Virtual serial port:** Elige `COM10`.
   - **Data source serial port:** Elige el COM real (`COM3`).
   - Parámetros: `9600`, `8`, `None`, `1` ➔ Pulsa **Finish**.
3. **Guardar Configuración:** Menú **File ➔ Save layout as...** ➔ Guardar en `C:\Utrecar\vspe_config.vspe`.

---

#### FASE 3: Verificación de Datos en Vivo con `test_rs485.py`
Ejecuta en PowerShell el monitor interactivo:
```powershell
python test_rs485.py
```
* El script detectará automáticamente el puerto virtual `COM10`. Pulsa Enter.
* Al descolgar o colgar una manguera en pista, verás en pantalla los paquetes en hexadecimal:
  `[0001] RECIBIDOS 14 BYTES ➔ HEX: 02 30 31 41 43 30 30 30 30 30 30 34 45 44 ...`
* Comprueba que el programa de caja de Aseproda sigue cobrando y emitiendo tickets con total normalidad.

---

#### FASE 4: Arranque del Agente de Sincronización Odoo Cloud
Para poner el agente a funcionar en segundo plano continuo sin ventanas abiertas:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_daemon.ps1
```
* El script copia automáticamente `agente_odoo_elcuervo.py` a `C:\Utrecar\` y lo ejecuta con `pythonw.exe` (modo invisible).
* **Comprobación de Logs:** Abre el archivo `C:\Utrecar\agente.log` con el Bloc de Notas. Verás:
  ```text
  INFO: Conectado a Odoo Cloud (https://odoo.utrecar.com). UID: 2
  INFO: Conectado al puerto COM10. Escuchando pista Aseproda y sincronizando con Odoo Cloud...
  ```

---

#### FASE 5: Configurar Persistencia 24/7 (Sobrevivir a Reinicios)
1. **Autostart de VSPE:**
   - Pulsa `Win + R` ➔ escribe `shell:startup` ➔ crea un acceso directo con destino:
     `"C:\Program Files\Eterlogic.com\VSPE\VSPEmulator.exe" -minimize -hide_splash "C:\Utrecar\vspe_config.vspe"`
2. **Autostart del Agente Odoo:**
   - Ejecuta en PowerShell como Administrador:
     ```powershell
     powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1
     ```

---

### 🌐 4. Parámetros de Producción Odoo Cloud
- **URL Servidor:** `https://odoo.utrecar.com`
- **Base de Datos:** `odoo`
- **Usuario Administrador:** `jarodriguezbonilla@gmail.com`
- **Contraseña:** `Utrecar2026!`
- **Punto de Venta:** `E.S. Rodalabota (El Cuervo)` (ID: `2`)
- **Módulo:** `pos_gas_station`
- **Puerto de Escucha:** `COM10` (Puerto Virtual Splitter)
- **Ruta de Logs Locales:** `C:\Utrecar\agente.log`
