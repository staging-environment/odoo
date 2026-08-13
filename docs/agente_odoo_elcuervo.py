import serial
import serial.tools.list_ports
import xmlrpc.client
import time
import logging
import os

os.makedirs(r'C:\Utrecar', exist_ok=True)

logging.basicConfig(
    filename=r'C:\Utrecar\agente.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s'
)

ODOO_URL = "https://odoo.utrecar.com"
DB_NAME = "odoo"
USER_LOGIN = "jarodriguezbonilla@gmail.com"
USER_PASS = "Utrecar2026!"

def auto_detect_port():
    for p in serial.tools.list_ports.comports():
        desc = p.description.lower()
        if "ftdi" in desc or "usb serial port" in desc or "0403:6001" in p.hwid.lower():
            return p.device
    return "COM3"

def connect_to_odoo():
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(DB_NAME, USER_LOGIN, USER_PASS, {})
        if uid:
            logging.info(f"✅ Conectado a Odoo Cloud ({ODOO_URL}). UID: {uid}")
            return uid
    except Exception as e:
        logging.error(f"❌ Error al autenticar en Odoo Cloud: {e}")
    return None

def start_agent():
    uid = connect_to_odoo()
    port = auto_detect_port()
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    
    try:
        ser = serial.Serial(port, baudrate=9600, timeout=1)
        logging.info(f"Escuchando pista en puerto {port} y sincronizando con Odoo Cloud...")
        
        while True:
            if ser.in_waiting > 0:
                raw_bytes = ser.read(ser.in_waiting)
                hex_data = " ".join([f"{b:02X}" for b in raw_bytes])
                
                if "45 4E 44" in hex_data:
                    try:
                        order_id = models.execute_kw(DB_NAME, uid, USER_PASS, 'pos.order', 'create', [{
                            'name': 'Manguerazo El Cuervo',
                            'station_code': 'EL_CUERVO',
                            'raw_hex': hex_data,
                            'note': 'Registrado automáticamente desde pista RS485'
                        }])
                        logging.info(f"✅ Venta registrada en Odoo Cloud con ID: {order_id}")
                    except Exception as odoo_err:
                        logging.error(f"Error creando venta en Odoo Cloud: {odoo_err}")
            time.sleep(0.05)
    except Exception as ser_err:
        logging.error(f"Error en puerto serie ({port}): {ser_err}")

if __name__ == "__main__":
    start_agent()
