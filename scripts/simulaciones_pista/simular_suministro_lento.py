"""Simula un suministro lento en una calle (ejecutar en el PC de pista, junto al agente).

Uso:  python simular_suministro_lento.py <calle> <importe_a_echar> [cod_producto=2] [precio=1.55] [paso=1.0]
  cod_producto: 1 = Gasóleo A (1.45), 2 = Sin Plomo 95 (1.55), 3 = Diesel Ultimate
Ej.:  python simular_suministro_lento.py 6 7 1 1.45 0.5   -> echa 7 € de Gasóleo A de 0,50 en 0,50 € y cuelga

Escribe C:\\Utrecar\\simular_venta_calle<N>.json, que el agente procesa (unhook -> dispensing -> ready).
Mientras dura, el agente ignora el microswitch real de esa calle. No envía órdenes al surtidor.
"""
import json, os, sys, time

CALLE = int(sys.argv[1]) if len(sys.argv) > 1 else 6
TOTAL = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
PROD = int(sys.argv[3]) if len(sys.argv) > 3 else 2
PRECIO = float(sys.argv[4]) if len(sys.argv) > 4 else 1.55
PASO = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0


def ev(estado, imp):
    data = {"calle": CALLE, "litros": round(imp / PRECIO, 2), "importe": round(imp, 2), "precio": PRECIO,
            "cod_producto": PROD, "estado": estado}
    tmp = f"C:\\Utrecar\\simular_venta_calle{CALLE}.tmp"
    tgt = f"C:\\Utrecar\\simular_venta_calle{CALLE}.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, tgt)
    print(time.strftime("%H:%M:%S"), estado, f"{imp:.2f} EUR / {data['litros']:.2f} L", flush=True)


ev("unhook", 0.0)
time.sleep(3)
imp = 0.0
while imp < TOTAL:
    imp = min(TOTAL, imp + PASO)
    ev("dispensing", imp)
    time.sleep(1)
time.sleep(3)
ev("ready", TOTAL)
