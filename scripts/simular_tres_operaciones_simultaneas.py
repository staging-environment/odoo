import json
import time
import os
import sys
import threading

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def escribir_evento(calle, data):
    tmp_file = f"C:\\Utrecar\\simular_venta_calle{calle}.tmp"
    tgt_file = f"C:\\Utrecar\\simular_venta_calle{calle}.json"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp_file, tgt_file)

def simular_calle_6():
    # Calle 6: Gasoil (Gasóleo A), autorizada 70€ libre, echa 70€ y cuelga
    calle = 6
    precio = 1.45
    prod = 1
    total_imp = 70.0
    total_lts = round(total_imp / precio, 2)  # 48.28 L

    print(f"⛽ [CALLE 6] Inicio: Cliente descuelga manguera de Gasóleo A (0.00 L)...")
    escribir_evento(calle, {
        "calle": calle,
        "litros": 0.0,
        "importe": 0.0,
        "precio": precio,
        "cod_producto": prod,
        "has_prepay": False,
        "preset_amount": 0.0,
        "estado": "unhook"
    })
    time.sleep(2.5)

    pasos = [
        (8.28, 12.00),
        (17.24, 25.00),
        (27.59, 40.00),
        (37.93, 55.00),
        (total_lts, total_imp)
    ]
    for lts, imp in pasos:
        escribir_evento(calle, {
            "calle": calle,
            "litros": lts,
            "importe": imp,
            "precio": precio,
            "cod_producto": prod,
            "has_prepay": False,
            "preset_amount": 0.0,
            "estado": "dispensing"
        })
        print(f"⛽ [CALLE 6 - Gasoil] Suministrando: {lts:.2f} L | {imp:.2f} €")
        time.sleep(2.5)

    time.sleep(1.5)
    print(f"🏁 [CALLE 6] Cliente cuelga manguera. Finalizado en {total_imp:.2f} € ({total_lts:.2f} L) -> COBRAR")
    escribir_evento(calle, {
        "calle": calle,
        "litros": total_lts,
        "importe": total_imp,
        "precio": precio,
        "cod_producto": prod,
        "has_prepay": False,
        "preset_amount": 0.0,
        "estado": "ready"
    })

def simular_calle_3():
    # Calle 3: Sin Plomo 95, prepago 50€, echa 50€ (completo) y cuelga
    calle = 3
    precio = 1.55
    prod = 2
    total_imp = 50.0
    total_lts = round(total_imp / precio, 2)  # 32.26 L

    print(f"⛽ [CALLE 3] Inicio: Cliente descuelga manguera de Sin Plomo 95 (0.00 L)...")
    escribir_evento(calle, {
        "calle": calle,
        "litros": 0.0,
        "importe": 0.0,
        "precio": precio,
        "cod_producto": prod,
        "has_prepay": True,
        "preset_amount": 50.0,
        "estado": "unhook"
    })
    time.sleep(2.5)

    pasos = [
        (5.48, 8.50),
        (11.61, 18.00),
        (18.71, 29.00),
        (25.81, 40.00),
        (total_lts, total_imp)
    ]
    for lts, imp in pasos:
        escribir_evento(calle, {
            "calle": calle,
            "litros": lts,
            "importe": imp,
            "precio": precio,
            "cod_producto": prod,
            "has_prepay": True,
            "preset_amount": 50.0,
            "estado": "dispensing"
        })
        print(f"⛽ [CALLE 3 - SP95] Suministrando: {lts:.2f} L | {imp:.2f} €")
        time.sleep(2.5)

    time.sleep(1.5)
    print(f"🏁 [CALLE 3] Cliente cuelga manguera. Prepago 50.00 € completado íntegramente -> Pista Liberada")
    escribir_evento(calle, {
        "calle": calle,
        "litros": total_lts,
        "importe": total_imp,
        "precio": precio,
        "cod_producto": prod,
        "has_prepay": True,
        "preset_amount": 50.0,
        "estado": "ready"
    })

def simular_calle_1():
    # Calle 1: Sin Plomo 95, autorizado 100€ prepago, echa 50€ (parcial) y cuelga
    calle = 1
    precio = 1.55
    prod = 2
    preset_imp = 100.0
    total_imp = 50.0
    total_lts = round(total_imp / precio, 2)  # 32.26 L

    print(f"⛽ [CALLE 1] Inicio: Cliente descuelga manguera de Sin Plomo 95 (0.00 L)...")
    escribir_evento(calle, {
        "calle": calle,
        "litros": 0.0,
        "importe": 0.0,
        "precio": precio,
        "cod_producto": prod,
        "has_prepay": True,
        "preset_amount": preset_imp,
        "estado": "unhook"
    })
    time.sleep(2.5)

    pasos = [
        (5.81, 9.00),
        (12.58, 19.50),
        (19.35, 30.00),
        (26.77, 41.50),
        (total_lts, total_imp)
    ]
    for lts, imp in pasos:
        escribir_evento(calle, {
            "calle": calle,
            "litros": lts,
            "importe": imp,
            "precio": precio,
            "cod_producto": prod,
            "has_prepay": True,
            "preset_amount": preset_imp,
            "estado": "dispensing"
        })
        print(f"⛽ [CALLE 1 - SP95] Suministrando: {lts:.2f} L | {imp:.2f} €")
        time.sleep(2.5)

    time.sleep(1.5)
    sobrante = preset_imp - total_imp
    print(f"🏁 [CALLE 1] Cliente cuelga manguera en {total_imp:.2f} € (de {preset_imp:.2f} € autorizados) -> SOBRANTE {sobrante:.2f} €")
    escribir_evento(calle, {
        "calle": calle,
        "litros": total_lts,
        "importe": total_imp,
        "precio": precio,
        "cod_producto": prod,
        "has_prepay": True,
        "preset_amount": preset_imp,
        "estado": "ready"
    })

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 INICIANDO SIMULACIÓN SIMULTÁNEA DE 3 PISTAS EN E.S. REPSOL (TRIESTE)")
    print("  - Calle 6: Autorizada con Gasoil -> Suministra 70.00 € y cuelga (Cobro)")
    print("  - Calle 3: Prepago 50.00 € Gasolina -> Suministra 50.00 € y cuelga (Completado)")
    print("  - Calle 1: Autorizada 100.00 € Gasolina -> Suministra 50.00 € y cuelga (Sobrante 50€)")
    print("=" * 70)

    t6 = threading.Thread(target=simular_calle_6, name="SimCalle6")
    t3 = threading.Thread(target=simular_calle_3, name="SimCalle3")
    t1 = threading.Thread(target=simular_calle_1, name="SimCalle1")

    # Iniciar las 3 simultáneamente
    t6.start()
    t3.start()
    t1.start()

    t6.join()
    t3.join()
    t1.join()

    print("\n" + "=" * 70)
    print("✅ SIMULACIÓN SIMULTÁNEA DE LAS 3 OPERACIONES FINALIZADA CON ÉXITO")
    print("=" * 70)
