# -*- coding: utf-8 -*-
"""
UTRECAR ERP - Publicador de impresoras instaladas en el PC de pista.

El navegador no puede enumerar las impresoras de Windows, así que este script
(Python puro, sin dependencias) las lee del registro de Windows y las publica
en Odoo en `ir.config_parameter` -> `pos_gas_station.system_printers_<config_id>`.
El TPV las muestra en "Configuración de Impresoras".

Es independiente del agente de pista (no hay que reiniciarlo).
Credenciales y CONFIG_ID se leen del agente de pista para no duplicarlas.

Uso:
    python agente_impresoras_pista.py           # bucle: publica cada 5 minutos
    python agente_impresoras_pista.py --once    # publica una vez y sale
    python agente_impresoras_pista.py --dry-run # solo muestra lo detectado
"""

import ast
import json
import os
import socket
import sys
import time
import xmlrpc.client

try:
    import winreg
except ImportError:  # permite importar el módulo fuera de Windows
    winreg = None

INTERVALO_SEG = 300
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
                impresoras.append({
                    "name": nombre,
                    "port": _reg_value(k, "Port"),
                    "driver": _reg_value(k, "Printer Driver"),
                    "type": clasificar(nombre),
                    "is_default": nombre == default,
                })
    impresoras.sort(key=lambda p: (not p["is_default"], p["type"] == "pdf", p["name"].lower()))
    return impresoras


def publicar(cfg, impresoras):
    common = xmlrpc.client.ServerProxy(f"{cfg['ODOO_URL']}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(cfg["DB_NAME"], cfg["USER_LOGIN"], cfg["USER_PASS"], {})
    if not uid:
        raise RuntimeError("Autenticación fallida en Odoo")
    models = xmlrpc.client.ServerProxy(f"{cfg['ODOO_URL']}/xmlrpc/2/object", allow_none=True)
    payload = {
        "hostname": socket.gethostname(),
        "updated_at": int(time.time()),
        "printers": impresoras,
    }
    models.execute_kw(cfg["DB_NAME"], uid, cfg["USER_PASS"], "ir.config_parameter", "set_param",
                      [f"pos_gas_station.system_printers_{cfg['CONFIG_ID']}", json.dumps(payload, ensure_ascii=False)])


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def main():
    args = set(sys.argv[1:])
    impresoras = detectar_impresoras()
    if "--dry-run" in args:
        print(json.dumps(impresoras, ensure_ascii=False, indent=2))
        return
    cfg = leer_config_agente()
    ultimo = None
    while True:
        try:
            impresoras = detectar_impresoras()
            # Republica si cambia la lista o cada hora (por si se borró el parámetro)
            firma = json.dumps(impresoras, sort_keys=True)
            if firma != ultimo or int(time.time()) % 3600 < INTERVALO_SEG:
                publicar(cfg, impresoras)
                ultimo = firma
                log(f"Publicadas {len(impresoras)} impresoras: " + ", ".join(p["name"] for p in impresoras))
        except Exception as e:
            log(f"ERROR: {e}")
        if "--once" in args:
            return
        time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()
