# -*- coding: utf-8 -*-
"""
UTRECAR ERP - Agente de impresoras del PC de pista.

1. Publica en Odoo las impresoras instaladas en Windows (el navegador no puede
   enumerarlas): `ir.config_parameter` -> `pos_gas_station.system_printers_<config_id>`.
2. Imprime los trabajos que el TPV deja en cola (`ir.attachment` con
   res_model = 'pos_gas_station.print_job'), cada uno en su impresora asignada:
     - application/vnd.escpos -> bytes ESC/POS enviados en RAW (térmica)
     - application/pdf        -> SumatraPDF en modo silencioso (A4)
   Si la impresora da error (sin papel, desconectada...) el trabajo se borra de la
   cola de Windows para no bloquearla y el error se devuelve al TPV.

Python puro (ctypes + winreg), sin dependencias. Independiente del agente de pista.
Credenciales y CONFIG_ID se leen del agente de pista para no duplicarlas.

Uso:
    python agente_impresoras_pista.py           # servicio: imprime y publica
    python agente_impresoras_pista.py --once    # publica impresoras una vez y sale
    python agente_impresoras_pista.py --dry-run # solo muestra lo detectado
"""

import ast
import base64
import ctypes
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import xmlrpc.client
from ctypes import wintypes

try:
    import winreg
except ImportError:  # permite importar el módulo fuera de Windows
    winreg = None

INTERVALO_SEG = 300          # republicar lista de impresoras
POLL_SEG = 2                 # consultar trabajos pendientes
LATIDO_SEG = 30              # avisar a Odoo de que el agente está vivo
ESPERA_TRABAJO_SEG = 45      # máximo que esperamos a que Windows imprima un trabajo
PRINT_JOB_MODEL = "pos_gas_station.print_job"
MIME_ESCPOS = "application/vnd.escpos"
MIME_PDF = "application/pdf"
SUMATRA_CANDIDATOS = [
    r"C:\Utrecar\SumatraPDF\SumatraPDF.exe",
    r"C:\Utrecar\SumatraPDF.exe",
    r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
]
PRINTERS_KEY = r"SYSTEM\CurrentControlSet\Control\Print\Printers"
VIRTUAL_HINTS = ("onenote", "pdf", "xps", "fax", "anydesk", "send to")
THERMAL_HINTS = ("pos80", "pos-80", "pos58", "tm-", "tm_", "thermal", "termica", "térmica", "ticket", "80mm", "58mm")

AGENTE_CANDIDATOS = [
    r"C:\agente_pista_odoo_bridge.py",
    r"C:\Utrecar\agente_pista_odoo_bridge.py",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "agente_pista_odoo_bridge.py"),
]


def leer_config_agente():
    """Extrae ODOO_URL, DB_NAME, USER_LOGIN, USER_PASS y CONFIG_ID del agente de pista sin ejecutarlo."""
    wanted = {"ODOO_URL", "DB_NAME", "USER_LOGIN", "USER_PASS", "CONFIG_ID"}
    for path in AGENTE_CANDIDATOS:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), path)
        cfg = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in wanted:
                    try:
                        cfg[name] = ast.literal_eval(node.value)
                    except ValueError:
                        pass
        if wanted <= cfg.keys():
            return cfg
    raise RuntimeError("No se encontró la configuración de Odoo en agente_pista_odoo_bridge.py")


def _reg_value(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return ""


def impresora_predeterminada():
    """Predeterminada del usuario interactivo si se puede, si no la de .DEFAULT (cuenta SYSTEM)."""
    candidatos = []
    try:
        with winreg.OpenKey(winreg.HKEY_USERS, "") as hku:
            i = 0
            while True:
                try:
                    sid = winreg.EnumKey(hku, i)
                except OSError:
                    break
                i += 1
                if sid.startswith("S-1-5-21-") and not sid.endswith("_Classes"):
                    candidatos.append(sid)
    except OSError:
        pass
    candidatos.append(".DEFAULT")
    for sid in candidatos:
        try:
            with winreg.OpenKey(winreg.HKEY_USERS, sid + r"\Software\Microsoft\Windows NT\CurrentVersion\Windows") as k:
                device = _reg_value(k, "Device")
                if device:
                    return device.split(",")[0].strip()
        except OSError:
            continue
    return ""


def clasificar(nombre):
    low = nombre.lower()
    if any(h in low for h in VIRTUAL_HINTS):
        return "pdf"
    if any(h in low for h in THERMAL_HINTS):
        return "thermal"
    return "laser_ink"


def _bandejas(nombre, puerto, timeout=10):
    """Bandejas que declara el driver (DC_BINNAMES). En un hilo con límite de tiempo:
    un driver colgado (p. ej. la Brother con el driver IPP genérico) no debe bloquear al agente."""
    resultado = []

    def consultar():
        try:
            ws = ctypes.WinDLL("winspool.drv")
            n = ws.DeviceCapabilitiesW(nombre, puerto, 12, None, None)  # DC_BINNAMES
            if n and n > 0:
                buf = ctypes.create_unicode_buffer(n * 24)
                ws.DeviceCapabilitiesW(nombre, puerto, 12, buf, None)
                for i in range(n):
                    b = ctypes.wstring_at(ctypes.addressof(buf) + i * 48, 24).split("\x00")[0].strip()
                    if b:
                        resultado.append(b)
        except Exception:
            pass

    hilo = threading.Thread(target=consultar, daemon=True)
    hilo.start()
    hilo.join(timeout)
    return list(resultado)


def detectar_impresoras():
    if winreg is None:
        raise RuntimeError("Este script solo funciona en Windows")
    default = impresora_predeterminada()
    impresoras = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PRINTERS_KEY) as root:
        i = 0
        while True:
            try:
                nombre = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            with winreg.OpenKey(root, nombre) as k:
                puerto = _reg_value(k, "Port")
                tipo = clasificar(nombre)
                impresoras.append({
                    "name": nombre,
                    "port": puerto,
                    "driver": _reg_value(k, "Printer Driver"),
                    "type": tipo,
                    "is_default": nombre == default,
                    "bins": _bandejas(nombre, puerto) if tipo == "laser_ink" else [],
                })
    impresoras.sort(key=lambda p: (not p["is_default"], p["type"] == "pdf", p["name"].lower()))
    return impresoras


# ---------------------------------------------------------------- Windows spooler (ctypes)
JOB_STATUS_ERROR = 0x2
JOB_STATUS_OFFLINE = 0x20
JOB_STATUS_PAPEROUT = 0x40
JOB_STATUS_BLOCKED = 0x200
JOB_STATUS_USER_INTERVENTION = 0x400
JOB_STATUS_DELETED = 0x100
JOB_STATUS_PRINTED = 0x80
JOB_STATUS_COMPLETE = 0x1000
JOB_ERRORES = (JOB_STATUS_ERROR | JOB_STATUS_OFFLINE | JOB_STATUS_PAPEROUT
               | JOB_STATUS_BLOCKED | JOB_STATUS_USER_INTERVENTION)
JOB_CONTROL_DELETE = 5


class DOC_INFO_1(ctypes.Structure):
    _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, wintypes.WORD) for n in ("wYear", "wMonth", "wDayOfWeek", "wDay",
                                              "wHour", "wMinute", "wSecond", "wMilliseconds")]


class JOB_INFO_1(ctypes.Structure):
    _fields_ = [("JobId", wintypes.DWORD), ("pPrinterName", wintypes.LPWSTR), ("pMachineName", wintypes.LPWSTR),
                ("pUserName", wintypes.LPWSTR), ("pDocument", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR),
                ("pStatus", wintypes.LPWSTR), ("Status", wintypes.DWORD), ("Priority", wintypes.DWORD),
                ("Position", wintypes.DWORD), ("TotalPages", wintypes.DWORD), ("PagesPrinted", wintypes.DWORD),
                ("Submitted", SYSTEMTIME)]


def _winspool():
    return ctypes.WinDLL("winspool.drv", use_last_error=True)


def _abrir_impresora(nombre):
    h = wintypes.HANDLE()
    if not _winspool().OpenPrinterW(nombre, ctypes.byref(h), None):
        raise RuntimeError(f"No se puede abrir la impresora '{nombre}' (error {ctypes.get_last_error()})")
    return h


def _trabajos(nombre):
    """Lista (JobId, Status, pStatus, pDocument) de la cola de Windows de esa impresora."""
    ws = _winspool()
    h = _abrir_impresora(nombre)
    try:
        needed, returned = wintypes.DWORD(), wintypes.DWORD()
        ws.EnumJobsW(h, 0, 255, 1, None, 0, ctypes.byref(needed), ctypes.byref(returned))
        if not needed.value:
            return []
        buf = ctypes.create_string_buffer(needed.value)
        if not ws.EnumJobsW(h, 0, 255, 1, buf, needed.value, ctypes.byref(needed), ctypes.byref(returned)):
            return []
        jobs = ctypes.cast(buf, ctypes.POINTER(JOB_INFO_1))
        return [(jobs[i].JobId, jobs[i].Status, jobs[i].pStatus or "", jobs[i].pDocument or "")
                for i in range(returned.value)]
    finally:
        ws.ClosePrinter(h)


def _borrar_trabajo(nombre, job_id):
    ws = _winspool()
    h = _abrir_impresora(nombre)
    try:
        ws.SetJobW(h, job_id, 0, None, JOB_CONTROL_DELETE)
    finally:
        ws.ClosePrinter(h)


def _describir_error(status, texto):
    if status & JOB_STATUS_PAPEROUT:
        return "La impresora no tiene papel"
    if status & JOB_STATUS_OFFLINE:
        return "La impresora está desconectada o apagada"
    if status & JOB_STATUS_USER_INTERVENTION:
        return "La impresora necesita atención (tapa abierta, atasco...)"
    return f"Error de impresora{(': ' + texto) if texto else ''} (desconectada, sin papel o apagada)"


def _esperar_trabajos(nombre, job_ids=None, desde_ids=None):
    """Espera a que los trabajos salgan de la cola. Si alguno entra en error, lo borra
    (para no bloquear la impresora) y lanza la excepción con el motivo."""
    limite = time.time() + ESPERA_TRABAJO_SEG
    pendientes = []
    while time.time() < limite:
        pendientes = []
        for jid, status, texto, _doc in _trabajos(nombre):
            nuestro = (job_ids and jid in job_ids) or (desde_ids is not None and jid not in desde_ids)
            if not nuestro:
                continue
            if status & JOB_ERRORES:
                _borrar_trabajo(nombre, jid)
                raise RuntimeError(_describir_error(status, texto))
            if not status & (JOB_STATUS_PRINTED | JOB_STATUS_COMPLETE | JOB_STATUS_DELETED):
                pendientes.append(jid)
        if not pendientes:
            return
        time.sleep(0.5)
    for jid in pendientes:
        _borrar_trabajo(nombre, jid)
    raise RuntimeError("La impresora no responde (trabajo cancelado tras %ss)" % ESPERA_TRABAJO_SEG)


def imprimir_raw(nombre, datos, titulo):
    ws = _winspool()
    h = _abrir_impresora(nombre)
    try:
        di = DOC_INFO_1(titulo[:60], None, "RAW")
        job_id = ws.StartDocPrinterW(h, 1, ctypes.byref(di))
        if not job_id:
            raise RuntimeError(f"No se pudo iniciar el trabajo (error {ctypes.get_last_error()})")
        ws.StartPagePrinter(h)
        escritos = wintypes.DWORD()
        ok = ws.WritePrinter(h, datos, len(datos), ctypes.byref(escritos))
        ws.EndPagePrinter(h)
        ws.EndDocPrinter(h)
        if not ok:
            raise RuntimeError(f"Error enviando datos a la impresora (error {ctypes.get_last_error()})")
    finally:
        ws.ClosePrinter(h)
    _esperar_trabajos(nombre, job_ids={job_id})


def _sumatra():
    for path in SUMATRA_CANDIDATOS:
        if os.path.isfile(path):
            return path
    raise RuntimeError("Falta SumatraPDF en el PC de pista (necesario para imprimir A4/PDF)")


def imprimir_pdf(nombre, datos, copias, bandeja="", papel=""):
    exe = _sumatra()
    previos = {jid for jid, *_ in _trabajos(nombre)}
    fd, path = tempfile.mkstemp(suffix=".pdf", prefix="utrecar_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(datos)
        try:
            ajustes = f"{int(copias)}x,fit"
            if bandeja:
                ajustes += f",bin={bandeja}"
            if papel:
                ajustes += f",paper={papel}"
            proc = subprocess.run([exe, "-print-to", nombre, "-print-settings", ajustes,
                                   "-silent", "-exit-when-done", path],
                                  timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise RuntimeError("La impresora no responde (su driver no contesta: revise que esté encendida y conectada)")
        if proc.returncode != 0:
            raise RuntimeError(f"SumatraPDF devolvió el código {proc.returncode}")
        _esperar_trabajos(nombre, desde_ids=previos)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------- Odoo
class Odoo:
    def __init__(self, cfg):
        self.cfg = cfg
        self.uid = None
        self.models = None

    def conectar(self):
        common = xmlrpc.client.ServerProxy(f"{self.cfg['ODOO_URL']}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.cfg["DB_NAME"], self.cfg["USER_LOGIN"], self.cfg["USER_PASS"], {})
        if not self.uid:
            raise RuntimeError("Autenticación fallida en Odoo")
        self.models = xmlrpc.client.ServerProxy(f"{self.cfg['ODOO_URL']}/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args, kw=None):
        if not self.uid:
            self.conectar()
        return self.models.execute_kw(self.cfg["DB_NAME"], self.uid, self.cfg["USER_PASS"], model, method, args, kw or {})

    def set_param(self, key, value):
        self.call("ir.config_parameter", "set_param", [key, value])


def pdf_disponible():
    return any(os.path.isfile(p) for p in SUMATRA_CANDIDATOS)


def publicar(odoo, impresoras):
    payload = {
        "hostname": socket.gethostname(),
        "updated_at": int(time.time()),
        "printers": impresoras,
        "pdf_ready": pdf_disponible(),
    }
    odoo.set_param(f"pos_gas_station.system_printers_{odoo.cfg['CONFIG_ID']}", json.dumps(payload, ensure_ascii=False))


_pdf_en_curso = threading.Event()


def _imprimir_trabajo(odoo, t, meta):
    impresora = meta.get("printer") or ""
    try:
        datos = base64.b64decode(t.get("datas") or b"")
        if t.get("mimetype") == MIME_ESCPOS:
            imprimir_raw(impresora, datos, t.get("name") or "Ticket")
        elif t.get("mimetype") == MIME_PDF:
            imprimir_pdf(impresora, datos, meta.get("copies") or 1, meta.get("tray") or "", meta.get("paper") or "")
        else:
            raise RuntimeError(f"Tipo de documento no soportado: {t.get('mimetype')}")
        odoo.call("ir.attachment", "unlink", [[t["id"]]])
        log(f"Impreso '{t.get('name')}' en {impresora}")
    except Exception as e:
        meta.update({"state": "error", "message": str(e)})
        odoo.call("ir.attachment", "write", [[t["id"]], {"description": json.dumps(meta, ensure_ascii=False)}])
        log(f"ERROR imprimiendo '{t.get('name')}' en {impresora}: {e}")


def _hilo_pdf(cfg, t, meta):
    # Conexión propia: xmlrpc.client no es seguro entre hilos
    try:
        _imprimir_trabajo(Odoo(cfg), t, meta)
    except Exception as e:
        log(f"ERROR en hilo PDF: {e}")
    finally:
        _pdf_en_curso.clear()


def procesar_trabajos(odoo):
    """Los tickets ESC/POS se imprimen en el momento; los PDF van de uno en uno en un hilo
    aparte para que un driver lento o colgado (A4) no retrase los tickets de la térmica."""
    cfg_id = odoo.cfg["CONFIG_ID"]
    trabajos = odoo.call("ir.attachment", "search_read",
                         [[("res_model", "=", PRINT_JOB_MODEL), ("res_id", "=", cfg_id),
                           ("description", "like", '"state": "pending"')]],
                         {"fields": ["id", "name", "mimetype", "description", "datas"], "order": "mimetype desc, id asc", "limit": 5})
    for t in trabajos:
        meta = json.loads(t.get("description") or "{}")
        es_pdf = t.get("mimetype") == MIME_PDF
        if es_pdf and _pdf_en_curso.is_set():
            continue  # se recogerá cuando termine el PDF en curso
        meta["state"] = "printing"
        odoo.call("ir.attachment", "write", [[t["id"]], {"description": json.dumps(meta, ensure_ascii=False)}])
        if es_pdf:
            _pdf_en_curso.set()
            threading.Thread(target=_hilo_pdf, args=(odoo.cfg, t, meta), daemon=True).start()
        else:
            _imprimir_trabajo(odoo, t, meta)


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def main():
    args = set(sys.argv[1:])
    impresoras = detectar_impresoras()
    if "--dry-run" in args:
        print(json.dumps(impresoras, ensure_ascii=False, indent=2))
        return
    odoo = Odoo(leer_config_agente())
    if "--once" in args:
        publicar(odoo, impresoras)
        log(f"Publicadas {len(impresoras)} impresoras: " + ", ".join(p["name"] for p in impresoras))
        return

    firma_publicada, ultimo_publicado, ultimo_latido = None, 0, 0
    log("Agente de impresoras iniciado")
    while True:
        try:
            ahora = time.time()
            if ahora - ultimo_latido >= LATIDO_SEG:
                odoo.set_param(f"pos_gas_station.print_agent_seen_{odoo.cfg['CONFIG_ID']}", str(int(ahora)))
                ultimo_latido = ahora
            if ahora - ultimo_publicado >= INTERVALO_SEG:
                impresoras = detectar_impresoras()
                firma = json.dumps([impresoras, pdf_disponible()], sort_keys=True)
                # Republica si cambia la lista o cada hora (por si se borró el parámetro)
                if firma != firma_publicada or int(ahora) % 3600 < INTERVALO_SEG:
                    publicar(odoo, impresoras)
                    firma_publicada = firma
                    log(f"Publicadas {len(impresoras)} impresoras: " + ", ".join(p["name"] for p in impresoras))
                ultimo_publicado = ahora
            procesar_trabajos(odoo)
        except Exception as e:
            log(f"ERROR: {e}")
            odoo.uid = None  # fuerza reconexión
            time.sleep(5)
        time.sleep(POLL_SEG)


if __name__ == "__main__":
    main()
