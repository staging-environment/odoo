"""Simula SOLO el microswitch: descuelga una manguera N segundos y la vuelve a colgar.

Uso:  python simular_descolgar_manguera.py <calle> [segundos=10]
No cambia el estado de la calle ni envía órdenes al surtidor. Si la calle no está autorizada ni
prepagada, el TPV debe sonar la alarma intermitente, parpadear y, al colgar, sonar el "finalizado".
"""
import json, os, sys, time

CALLE = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SEGUNDOS = float(sys.argv[2]) if len(sys.argv) > 2 else 10


def ev(estado):
    data = {"calle": CALLE, "estado": estado}
    tmp = f"C:\\Utrecar\\simular_venta_calle{CALLE}.tmp"
    tgt = f"C:\\Utrecar\\simular_venta_calle{CALLE}.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, tgt)
    print(time.strftime("%H:%M:%S"), estado, flush=True)


ev("descolgar")
time.sleep(SEGUNDOS)
ev("colgar")
