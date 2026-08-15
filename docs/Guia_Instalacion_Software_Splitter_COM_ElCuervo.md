# UTRECAR ERP — Integración Aseproda & Odoo Cloud (E.S. Rodalabota - El Cuervo)
## 🔌 Guía Técnica: Divisor Virtual de Puerto COM (100% Software)

---

### 📌 Objetivo de esta Solución
Eliminar la necesidad de añadir resistencias o modificar el cableado físico de pista. La caja negra de Aseproda ya está conectada por cable USB al TPV principal. Utilizando un **Splitter Virtual de Puerto COM (VSPE)**, el software de Aseproda y nuestro agente de Odoo leen simultáneamente los mismos datos de los surtidores sin cortes de servicio ni bloqueos del bus RS-485.

---

### 1. ¿Por qué ocurre el bloqueo y cómo lo soluciona el Splitter?
* **Causa del bloqueo:** Al conectar un segundo conversor USB-RS485 en paralelo con la caja de Aseproda, se colocan dos resistencias de terminación de 120 Ω y dos redes de polarización activa en la misma línea física. Esto genera una **sobrecarga de impedancia que desploma el voltaje del bus**, impidiendo que el TPV reciba respuesta de los surtidores.
* **Solución por software:** La caja negra ya digitaliza las señales de pista y las envía al TPV principal por su propio cable USB. Con un **emulador virtual de puertos COM**, clonamos ese flujo de datos para que dos programas lo abran simultáneamente sin conflictos de Windows.

```
[Surtidores Pista] ==(RS-485)==> [Caja Negra Aseproda] ==(USB)==> [COM3 Físico en TPV]
                                                                        │
                                                                        ▼
                                                            [VSPE / Splitter Virtual]
                                                                  ┌─────┴─────┐
                                                                  ▼           ▼
                                                           [Virtual COM10] [Virtual COM10]
                                                                  │           │
                                                                  ▼           ▼
                                                           [TPV Aseproda] [Agente Odoo Cloud]
```

---

### 2. Paso 1: Identificar el puerto COM real de la Caja Aseproda
1. Pulsa **Win + X** en el TPV principal y selecciona **Administrador de Dispositivos** (o pulsa *Win + R* y escribe `devmgmt.msc`).
2. Despliega la categoría **Puertos (COM y LPT)**.
3. **Comprobación:** Desconecta el cable USB de la caja negra durante 2 segundos y reconéctalo. Observa qué puerto desaparece y reaparece (ejemplo: `COM3` o `COM1`). Anota ese puerto.
4. Clic derecho sobre el puerto ➔ *Propiedades* ➔ *Configuración de puerto*. Verifica velocidad (estándar: **9600 baudios**, 8 bits, Sin paridad, 1 bit parada).

---

### 3. Paso 2: Descargar e Instalar VSPE (Virtual Serial Ports Emulator)
* **Descarga:** Descargar el instalador desde la web oficial de Eterlogic:
  **http://www.eterlogic.com/Products.VSPE.html** (Descargar versión de 32 o 64 bits según el Windows del TPV).
* **Instalación:** Ejecutar `SetupVSPE.exe` como Administrador y completar el asistente (*Next ➔ Accept ➔ Install*).
* **Controladores:** Si Windows solicita confirmación para instalar controladores de dispositivos virtuales serie, marcar **Confiar e Instalar**.

---

### 4. Paso 3: Configurar el Dispositivo tipo Splitter en VSPE
1. Abre **VSPE** (icono en escritorio o menú Inicio) ejecutándolo como Administrador.
2. Haz clic en el menú **Device ➔ Create...** (o pulsa el icono de nuevo dispositivo).
3. En el desplegable *Device type*, selecciona **Splitter** y pulsa **Next**.
4. **Configuración de parámetros:**
   * **Virtual serial port:** Selecciona un puerto virtual libre (ejemplo: `COM10`).
   * **Data source serial port:** Selecciona el puerto real de la caja Aseproda (ejemplo: `COM3`).
   * **Baud rate:** `9600` | **Data bits:** `8` | **Parity:** `None` | **Stop bits:** `1`
   * Pulsa **Finish**.
5. En la lista de dispositivos de VSPE, verificarás que el estado indica **INITIALIZED (OK)** con icono verde.
6. Guarda la configuración: Menú **File ➔ Save layout as...** y guárdalo en `C:\Utrecar\vspe_config.vspe`.

---

### 5. Paso 4: Conectar TPV Aseproda y Agente Odoo a COM10
| Aplicación | Puerto | Función en la Estación |
| :--- | :---: | :--- |
| **TPV Aseproda** (Programa de Caja) | `COM10` | Sigue operando normalmente. Gestiona cobros, ticketera y órdenes de surtidor sin alteraciones. |
| **Agente Odoo** (`agente_odoo_elcuervo.py`) | `COM10` | Lee las tramas de pista en tiempo real y sube automáticamente los manguerazos a **https://odoo.utrecar.com**. |

---

### 6. Paso 5: Autoinicio 24/7 frente a Reinicios del TPV
1. **Arranque VSPE:**
   * Pulsa **Win + R**, escribe `shell:startup` y pulsa Enter.
   * En esa carpeta, crea un acceso directo a VSPE con el siguiente destino:
     `"C:\Program Files\Eterlogic.com\VSPE\VSPEmulator.exe" -minimize -hide_splash "C:\Utrecar\vspe_config.vspe"`
     *(Arranca en silencio minimizado en la bandeja del sistema y activa el puerto virtual automáticamente)*.
2. **Arranque Agente Odoo:**
   * Ejecuta en PowerShell el instalador de tarea programada ya preparado:
     `powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1`

---

### 7. Checklist de Comprobación en Vivo
- [x] **Paso 1:** Desconectar USB azul externo (dejar cableado físico tal como está).
- [x] **Paso 2:** Identificar puerto COM de caja negra en Administrador de Dispositivos.
- [x] **Paso 3:** Instalar VSPE y crear Splitter (Origen: COM real ➔ Virtual: COM10).
- [x] **Paso 4:** Ejecutar `python test_rs485.py` apuntando a COM10 y verificar lectura.
- [x] **Paso 5:** Verificar que TPV Aseproda cobra y descuelga mangueras en pista.
- [x] **Paso 6:** Configurar acceso directo en `shell:startup` para VSPE.
