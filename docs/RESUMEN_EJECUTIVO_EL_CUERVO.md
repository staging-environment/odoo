# RESUMEN EJECUTIVO & CONTEXTO PERSISTENTE - PROYECTO PISTA EL CUERVO

## 📌 Datos de Producción (Odoo Cloud)
- **URL Servidor Odoo Cloud:** `https://odoo.utrecar.com`
- **Base de Datos:** `odoo`
- **Usuario Administrador:** `jarodriguezbonilla@gmail.com`
- **Contraseña:** `Utrecar2026!`
- **Punto de Venta Creado:** `E.S. Rodalabota (El Cuervo)` (ID: `2`)
- **Módulo de Gasolinera:** `pos_gas_station` (Instalado y activado)
- **Puerto Serie Virtual:** `COM10` (VSPE Splitter vinculado al COM real de Aseproda)

---

## 🛠️ Hardware & Conexión (1 Solo Cable USB)
- **Ubicación:** E.S. Rodalabota (El Cuervo), Sevilla.
- **Conexión:** 1 solo cable USB conectado entre la caja negra de Aseproda y el TPV principal.
- **Virtualización:** Splitter por software (VSPE) que clona el puerto real (ej. `COM3`) a `COM10` para que el programa de caja de Aseproda y el agente de Odoo lean en paralelo sin sobrecargar el bus RS-485.

---

## 💻 Protocolo de Despliegue en PowerShell (Secuencia Ordenada 1 a 5)

| Orden | Archivo Script | Propósito | Comando Exacto en PowerShell |
| :---: | :--- | :--- | :--- |
| **PASO 1** | **`install_prerequisites.ps1`** | Instala Python 3.12, PySerial y Requests en 1 clic. | `powershell -ExecutionPolicy Bypass -File .\install_prerequisites.ps1` |
| **PASO 2** | *(Software VSPE)* | Crea Splitter Virtual (Origen: COM real ➔ Virtual: `COM10`). | *(Configurar VSPE y guardar `C:\Utrecar\vspe_config.vspe`)* |
| **PASO 3** | **`test_rs485.py`** | Monitor en tiempo real para verificar tramas HEX en `COM10`. | `python test_rs485.py` |
| **PASO 4** | **`start_daemon.ps1`** | Arranca `agente_odoo_elcuervo.py` en 2º plano invisible. | `powershell -ExecutionPolicy Bypass -File .\start_daemon.ps1` |
| **PASO 5** | **`setup_task_scheduler.ps1`** | Registra la Tarea Programada de Windows para autostart 24/7. | `powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1` |

---

## ⏱️ Cronograma de Señales de Surtidores (Aseproda Hexadecimal)
- **Idle / Reposo (`02 30 31 41 43...`):** Polling constante cada 0.5s-1s.
- **Descolgado (`02 30 31 53 54...`):** Manguera levantada en pista.
- **Repostaje (`02 30 31 44 41...`):** Conteo de litros e importe en tiempo real.
- **Fin de Venta (`02 30 31 45 4E 44...`):** Manguera colgada. Envío automático a Odoo Cloud (`https://odoo.utrecar.com`).

---

## 📄 Archivos Manuales de Referencia en `docs/`
- **`docs/Guia_Instalacion_Software_Splitter_COM_ElCuervo.pdf`** (Manual completo de despliegue con Splitter y orden de scripts).
- **`docs/Guia_Instalacion_Software_Splitter_COM_ElCuervo.md`** (Versión Markdown técnica).
