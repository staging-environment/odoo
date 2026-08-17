import serial
import serial.tools.list_ports
import time

def auto_detect_port():
    available = [p.device for p in serial.tools.list_ports.comports()]
    if "COM10" in available:
        return "COM10", "Puerto Virtual VSPE Splitter"
    for p in serial.tools.list_ports.comports():
        desc = p.description.lower()
        if "vspe" in desc or "virtual" in desc or "ftdi" in desc or "usb serial port" in desc or "dsd" in desc:
            return p.device, p.description
    usb_ports = [p for p in serial.tools.list_ports.comports() if p.device != "COM1"]
    if usb_ports:
        return usb_ports[0].device, usb_ports[0].description
    return "COM10", "Puerto Virtual por Defecto"

print("=" * 60)
print("   UTRECAR ERP - PRUEBA DE CAPTURA RS485 / VSPE (EL CUERVO)")
print("=" * 60)

detected_port, port_desc = auto_detect_port()
print(f"\nPuerto Detectado: {detected_port} ({port_desc})")
port_name = input(f"Introduce puerto o pulsa ENTER para usar [{detected_port}]: ").strip() or detected_port

baud_rate = 9600

try:
    ser = serial.Serial(port_name, baudrate=baud_rate, timeout=1)
    print(f"\n✅ Conectado a {port_name} a {baud_rate} baudios. Escuchando pista en vivo...\n")
    
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
    print(f"\n❌ Error al abrir {port_name}: {e}")
