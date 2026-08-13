import serial
import serial.tools.list_ports
import time

def auto_detect_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "ftdi" in desc or "usb serial port" in desc or "dsd" in desc or "0403:6001" in p.hwid.lower():
            return p.device, p.description
    usb_ports = [p for p in ports if p.device != "COM1"]
    if usb_ports:
        return usb_ports[0].device, usb_ports[0].description
    return None, None

print("=" * 60)
print("   UTRECAR ERP - PRUEBA DE CAPTURA RS485 (EL CUERVO)")
print("=" * 60)

detected_port, port_desc = auto_detect_port()
if detected_port:
    print(f"\n✅ Puerto DSD TECH Auto-Detectado: {detected_port} ({port_desc})")
    port_name = detected_port
else:
    port_name = input("\nNo se autodetectó. Introduce puerto (ej. COM3): ").strip() or "COM3"

baud_rate = 9600

try:
    ser = serial.Serial(port_name, baudrate=baud_rate, timeout=1)
    print(f"✅ Conectado a {port_name} a {baud_rate} baudios. Escuchando pista...\n")
    
    count = 0
    while True:
        if ser.in_waiting > 0:
            raw_bytes = ser.read(ser.in_waiting)
            count += 1
            hex_str = " ".join([f"{b:02X}" for b in raw_bytes])
            print(f"[{count:04d}] RECIBIDOS {len(raw_bytes):2d} BYTES ➔ HEX: {hex_str}")
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nPrueba finalizada por el usuario.")
except Exception as e:
    print(f"\n❌ Error: {e}")
