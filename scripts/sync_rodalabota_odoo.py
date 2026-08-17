import os
import time
import json
import logging
import pymysql
import xmlrpc.client
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- CONFIGURACION ODOO CLOUD ---
ODOO_URL = "https://odoo.utrecar.com"
ODOO_DB = "odoo"
ODOO_USER = "jarodriguezbonilla@gmail.com"
ODOO_PASS = "Utrecar2026!"
POS_CONFIG_ID = 2  # E.S. Rodalabota (El Cuervo)

# --- CONFIGURACION BASE DE DATOS LOCAL VIRTUSGESNET (MARIADB) ---
DB_HOST = "127.0.0.1"
DB_PORT = 33061
DB_USER = "root"
DB_PASS = ".root."
DB_NAME = "virtusgesnet"
STATION_CODE = 3  # E.S. RODALABOTA

STATE_FILE = "/opt/utrecar/sync_state_rodalabota.json"

def get_odoo_connection():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def ensure_pos_session(uid, models):
    # Buscar si hay sesion abierta para el POS 2
    sessions = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.session', 'search_read',
        [[('config_id', '=', POS_CONFIG_ID), ('state', '=', 'opened')]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    if sessions:
        return sessions[0]['id']
    
    # Si no hay sesion abierta, buscar la ultima no cerrada o abrir una nueva
    existing = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.session', 'search_read',
        [[('config_id', '=', POS_CONFIG_ID), ('state', '!=', 'closed')]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    if existing:
        return existing[0]['id']
    
    # Crear y abrir sesion nueva
    session_id = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.session', 'create',
        [{'user_id': uid, 'config_id': POS_CONFIG_ID}]
    )
    logging.info(f"Creada nueva sesion POS ID {session_id} para Rodalabota")
    return session_id

def ensure_odoo_fuel_products(uid, models):
    product_map = {}
    products = [
        {"code": "1", "name": "Gasóleo A", "ref": "GAS_A", "price": 1.45},
        {"code": "2", "name": "Sin Plomo 95", "ref": "SP95", "price": 1.55},
        {"code": "3", "name": "Gasóleo B", "ref": "GAS_B", "price": 1.10},
        {"code": "4", "name": "Gasóleo Plus", "ref": "GAS_PLUS", "price": 1.55},
    ]
    for p in products:
        found = models.execute_kw(
            ODOO_DB, uid, ODOO_PASS, 'product.product', 'search_read',
            [[('name', '=', p['name'])]],
            {'fields': ['id', 'name'], 'limit': 1}
        )
        if found:
            product_map[p['code']] = found[0]['id']
        else:
            new_id = models.execute_kw(
                ODOO_DB, uid, ODOO_PASS, 'product.product', 'create',
                [{
                    'name': p['name'],
                    'default_code': p['ref'],
                    'list_price': p['price'],
                    'available_in_pos': True,
                    'type': 'consu'
                }]
            )
            product_map[p['code']] = new_id
            logging.info(f"Creado producto {p['name']} en Odoo (ID: {new_id})")
            
    # Default fallback
    found_generic = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'product.product', 'search_read',
        [[('name', '=', 'Carburante Pista')]],
        {'fields': ['id'], 'limit': 1}
    )
    if found_generic:
        product_map['default'] = found_generic[0]['id']
    else:
        gid = models.execute_kw(
            ODOO_DB, uid, ODOO_PASS, 'product.product', 'create',
            [{'name': 'Carburante Pista', 'available_in_pos': True, 'type': 'consu'}]
        )
        product_map['default'] = gid
        
    return product_map

def get_last_synced_id():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return data.get("last_detalle_id", 0)
        except Exception:
            pass
    return 0

def save_last_synced_id(last_id):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"last_detalle_id": last_id, "updated_at": datetime.now().isoformat()}, f)

def sync_loop():
    logging.info("🚀 Iniciando servicio de sincronización Aseproda (Rodalabota) ➔ Odoo Cloud...")
    
    uid, models = get_odoo_connection()
    logging.info(f"✅ Conectado a Odoo Cloud con UID {uid}")
    
    session_id = ensure_pos_session(uid, models)
    logging.info(f"✅ Sesion POS Rodalabota activa: {session_id}")
    
    product_map = ensure_odoo_fuel_products(uid, models)
    logging.info(f"✅ Mapeo de productos Odoo listo: {product_map}")
    
    # Obtener metodo de pago permitido para este POS especifico
    pos_cfg = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.config', 'read',
        [[POS_CONFIG_ID]], {'fields': ['payment_method_ids']}
    )
    allowed_pm_ids = pos_cfg[0]['payment_method_ids'] if pos_cfg else []
    default_pay_id = allowed_pm_ids[0] if allowed_pm_ids else False
    logging.info(f"✅ Metodo de pago configurado en POS 2: {default_pay_id}")
    
    last_id = get_last_synced_id()
    if last_id == 0:
        try:
            conn = pymysql.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME
            )
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(d.Id) FROM detalledefacturasyticketsdeventa d "
                    "JOIN facturasyticketsdeventa f ON d.Serie = f.Serie AND d.Numero = f.Numero "
                    "WHERE f.CodigoDeEstacion = %s", (STATION_CODE,)
                )
                res = cursor.fetchone()
                max_id = res[0] or 0
                last_id = max_id - 3  # Importar los últimos 3 tickets para verificar de inmediato
                if last_id < 0: last_id = 0
                save_last_synced_id(last_id)
                logging.info(f"Inicializado ID de sincronización en: {last_id} (Max ID: {max_id})")
            conn.close()
        except Exception as e:
            logging.error(f"Error al inicializar ID: {e}")

    while True:
        try:
            conn = pymysql.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME,
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cursor:
                query = """
                    SELECT d.Id as DetalleId, d.Serie, d.Numero, d.CodigoDeProducto, d.Cantidad, 
                           d.Precio, d.Importe, d.PorcentajeDeIva, f.FechaYHora, f.Matricula, 
                           f.ImporteTotal, f.CodigoDeFormaDePago
                    FROM detalledefacturasyticketsdeventa d
                    JOIN facturasyticketsdeventa f ON d.Serie = f.Serie AND d.Numero = f.Numero
                    WHERE f.CodigoDeEstacion = %s AND d.Id > %s
                    ORDER BY d.Id ASC
                    LIMIT 20
                """
                cursor.execute(query, (STATION_CODE, last_id))
                rows = cursor.fetchall()
                
                for row in rows:
                    det_id = row['DetalleId']
                    serie = row['Serie']
                    numero = row['Numero']
                    prod_code = str(row['CodigoDeProducto'])
                    litros = float(row['Cantidad'] or 0.0)
                    precio_unit = float(row['Precio'] or 0.0)
                    total_eur = float(row['Importe'] or row['ImporteTotal'] or 0.0)
                    fecha_str = str(row['FechaYHora'] or datetime.now())
                    matricula = row['Matricula'] or ""
                    
                    odoo_prod_id = product_map.get(prod_code, product_map.get('default'))
                    
                    session_id = ensure_pos_session(uid, models)
                    
                    order_data = {
                        'name': f"Rodalabota {serie}-{numero}",
                        'pos_reference': f"Ticket {serie}-{numero}",
                        'session_id': session_id,
                        'amount_total': total_eur,
                        'amount_tax': round(total_eur * 0.21 / 1.21, 2),
                        'amount_paid': total_eur,
                        'amount_return': 0.0,
                        'lines': [
                            (0, 0, {
                                'product_id': odoo_prod_id,
                                'qty': litros if litros > 0 else 1.0,
                                'price_unit': precio_unit if precio_unit > 0 else total_eur,
                                'price_subtotal': round(total_eur / 1.21, 2),
                                'price_subtotal_incl': total_eur,
                            })
                        ],
                        'payment_ids': [
                            (0, 0, {
                                'payment_method_id': default_pay_id,
                                'amount': total_eur,
                                'payment_date': fecha_str,
                            })
                        ] if default_pay_id else []
                    }
                    
                    try:
                        order_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'pos.order', 'create', [order_data])
                        logging.info(f"✅ VENTA EN ODOO -> Ticket {serie}-{numero} | {litros:.2f}L | {total_eur:.2f}€ | Odoo ID: {order_id}")
                    except Exception as odoo_err:
                        logging.error(f"❌ Error al crear pedido en Odoo para Ticket {serie}-{numero}: {odoo_err}")
                        
                    last_id = det_id
                    save_last_synced_id(last_id)
            conn.close()
        except Exception as err:
            logging.error(f"Error en bucle de captura: {err}")
            
        time.sleep(1)

if __name__ == "__main__":
    sync_loop()
