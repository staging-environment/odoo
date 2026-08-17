import os
import time
import json
import logging
import pymysql
import xmlrpc.client
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- CONFIGURACION ODOO CLOUD ---
ODOO_URL = "https://odoo.utrecar.com"
ODOO_DB = "odoo"
ODOO_USER = "jarodriguezbonilla@gmail.com"
ODOO_PASS = "Utrecar2026!"

# --- CONFIGURACION BASE DE DATOS LOCAL VIRTUSGESNET (MARIADB) ---
DB_HOST = "127.0.0.1"
DB_PORT = 33061
DB_USER = "root"
DB_PASS = ".root."
DB_NAME = "virtusgesnet"

STATE_FILE = "/opt/utrecar/sync_state_all_stations.json"

STATIONS = [
    {
        "code": 1,
        "name": "E.S. Vistalegre (Utrera)",
        "pos_id": 3,
        "calles": [1, 2, 3, 4]
    },
    {
        "code": 2,
        "name": "E.S. Ronda Norte",
        "pos_id": 5,
        "calles": [1, 2, 3, 4, 5, 6, 7, 8]
    },
    {
        "code": 3,
        "name": "E.S. Rodalabota (El Cuervo)",
        "pos_id": 2,
        "calles": [1, 2, 3, 4]
    },
    {
        "code": 4,
        "name": "E.S. Atenas (Écija)",
        "pos_id": 6,
        "calles": [1, 2, 3, 4]
    }
]

def get_odoo_connection():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def ensure_pos_session(uid, models, pos_config_id):
    sessions = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.session', 'search_read',
        [[('config_id', '=', pos_config_id), ('state', '=', 'opened')]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    if sessions:
        return sessions[0]['id']
    
    existing = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.session', 'search_read',
        [[('config_id', '=', pos_config_id), ('state', '!=', 'closed')]],
        {'fields': ['id', 'name'], 'limit': 1}
    )
    if existing:
        return existing[0]['id']
    
    session_id = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'pos.session', 'create',
        [{'user_id': uid, 'config_id': pos_config_id}]
    )
    logging.info(f"Creada nueva sesion POS ID {session_id} para POS Config {pos_config_id}")
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

def get_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_live_pumps_state(conn, station_cfg, product_map):
    pumps = []
    fuel_names = {"1": "Gasóleo A", "2": "Sin Plomo 95", "3": "Gasóleo B"}
    st_code = station_cfg["code"]
    
    with conn.cursor() as cursor:
        for calle in station_cfg["calles"]:
            cursor.execute("""
                SELECT id, CodigoDeMaquinaExpendedora, NumeroDeContador, CodigoDeProducto, 
                       CantidadExpedida, Precio, ImporteExpedido, CantidadPrefijada, ImportePrefijado,
                       FechaYHoraDeExpedicion, FechaYHoraDePrefijado, Estado
                FROM expediciones
                WHERE CodigoDeEstacion = %s AND CodigoDeMaquinaExpendedora = %s
                ORDER BY id DESC
                LIMIT 1
            """, (st_code, calle))
            row = cursor.fetchone()
            
            p_state = {
                'id': calle,
                'name': f"Calle {calle}",
                'fuel': "Gasóleo A / Sin Plomo 95",
                'amount': 0.0,
                'liters': 0.0,
                'status': 'idle',
                'statusText': 'LIBRE',
                'product_id': product_map.get('1', product_map.get('default')),
                'price': 1.769
            }
            
            if row:
                prod_code = str(row['CodigoDeProducto'])
                fuel_name = fuel_names.get(prod_code, "Gasóleo A")
                amount = float(row['ImporteExpedido'] or 0.0)
                liters = float(row['CantidadExpedida'] or 0.0)
                pref_amount = float(row['ImportePrefijado'] or 0.0)
                pref_liters = float(row['CantidadPrefijada'] or 0.0)
                price = float(row['Precio'] or (amount / liters if liters > 0 else 1.769))
                exp_date = row['FechaYHoraDeExpedicion'] or row['FechaYHoraDePrefijado']
                estado = row['Estado']
                
                is_recent = False
                if exp_date:
                    delta = datetime.now() - exp_date
                    if abs(delta.total_seconds()) < 180:
                        is_recent = True
                
                if estado == 'Prefijado' and is_recent:
                    p_state['status'] = 'dispensing'
                    p_state['statusText'] = 'AUTORIZADO'
                    p_state['amount'] = pref_amount if pref_amount > 0 else amount
                    p_state['liters'] = pref_liters if pref_liters > 0 else round(pref_amount / price, 2) if price > 0 else 0.0
                    p_state['fuel'] = fuel_name
                elif estado == 'En expedicion':
                    p_state['status'] = 'dispensing'
                    p_state['statusText'] = 'SUMINISTRANDO'
                    p_state['amount'] = amount if amount > 0 else pref_amount
                    p_state['liters'] = liters if liters > 0 else (pref_amount / price if price > 0 else 0.0)
                    p_state['fuel'] = fuel_name
                elif is_recent and (amount > 0 or pref_amount > 0):
                    p_state['status'] = 'ready'
                    p_state['statusText'] = 'PENDIENTE DE COBRO'
                    p_state['amount'] = amount if amount > 0 else pref_amount
                    p_state['liters'] = liters if liters > 0 else (pref_amount / price if price > 0 else 0.0)
                    p_state['fuel'] = fuel_name
                else:
                    p_state['status'] = 'idle'
                    p_state['statusText'] = 'LIBRE'
                    p_state['amount'] = 0.0
                    p_state['liters'] = 0.0
                    p_state['fuel'] = "Gasóleo A / Sin Plomo 95"
                    
                p_state['product_id'] = product_map.get(prod_code, product_map.get('default'))
                p_state['price'] = price
                
            pumps.append(p_state)
            
    return {
        'station_name': f"CONTROL DE PISTA - {station_cfg['name'].upper()}",
        'pumps': pumps
    }

def sync_loop():
    logging.info("🚀 Iniciando Sincronizador Global Multigasolinera (4 Estaciones) ➔ Odoo Cloud...")
    
    uid, models = get_odoo_connection()
    logging.info(f"✅ Conectado a Odoo Cloud con UID {uid}")
    
    product_map = ensure_odoo_fuel_products(uid, models)
    logging.info(f"✅ Mapeo de productos Odoo listo: {product_map}")
    
    # Cache de metodos de pago por POS Config
    pay_method_map = {}
    for st in STATIONS:
        pos_id = st["pos_id"]
        cfg = models.execute_kw(
            ODOO_DB, uid, ODOO_PASS, 'pos.config', 'read',
            [[pos_id]], {'fields': ['payment_method_ids']}
        )
        pms = cfg[0]['payment_method_ids'] if cfg else []
        pay_method_map[pos_id] = pms[0] if pms else False
        logging.info(f"✅ POS ID {pos_id} ({st['name']}) -> Metodo de pago: {pay_method_map[pos_id]}")
        
    state = get_state()
    
    # Inicializar IDs de sincronizacion si no existen
    try:
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME
        )
        with conn.cursor() as cursor:
            for st in STATIONS:
                key = f"st_{st['code']}_last_id"
                if key not in state:
                    cursor.execute(
                        "SELECT MAX(d.Id) FROM detalledefacturasyticketsdeventa d "
                        "JOIN facturasyticketsdeventa f ON d.Serie = f.Serie AND d.Numero = f.Numero "
                        "WHERE f.CodigoDeEstacion = %s", (st['code'],)
                    )
                    res = cursor.fetchone()
                    state[key] = res[0] or 0
                    logging.info(f"Inicializado ID para {st['name']}: {state[key]}")
        conn.close()
        save_state(state)
    except Exception as e:
        logging.error(f"Error al inicializar estados: {e}")

    last_pumps_state_cache = {}

    while True:
        try:
            conn = pymysql.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME,
                cursorclass=pymysql.cursors.DictCursor
            )
            
            for st in STATIONS:
                st_code = st["code"]
                pos_id = st["pos_id"]
                st_name = st["name"]
                key = f"st_{st_code}_last_id"
                last_id = state.get(key, 0)
                
                # 1. ACTUALIZAR ESTADO EN VIVO DE LAS PISTAS
                try:
                    live_state = get_live_pumps_state(conn, st, product_map)
                    state_json = json.dumps(live_state)
                    if last_pumps_state_cache.get(pos_id) != state_json:
                        models.execute_kw(
                            ODOO_DB, uid, ODOO_PASS, 'ir.config_parameter', 'set_param',
                            [f'pos_gas_station.pumps_state_{pos_id}', state_json]
                        )
                        last_pumps_state_cache[pos_id] = state_json
                except Exception as live_err:
                    logging.debug(f"Error al actualizar estado en vivo de {st_name}: {live_err}")
                    
                # 2. CAPTURAR VENTAS COMPLETADAS
                try:
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
                        cursor.execute(query, (st_code, last_id))
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
                            session_id = ensure_pos_session(uid, models, pos_id)
                            pos_ref = f"{pos_id:05d}-{session_id:04d}-{det_id:08d}"
                            
                            pay_id = pay_method_map.get(pos_id)
                            order_data = {
                                'name': f"{st_name} {serie}-{numero}",
                                'pos_reference': pos_ref,
                                'session_id': session_id,
                                'state': 'paid',
                                'amount_total': total_eur,
                                'amount_tax': round(total_eur * 0.21 / 1.21, 2),
                                'amount_paid': total_eur,
                                'amount_return': 0.0,
                                'note': f"Ticket {serie}-{numero}" + (f" | Matricula: {matricula}" if matricula else ""),
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
                                        'payment_method_id': pay_id,
                                        'amount': total_eur,
                                        'payment_date': fecha_str,
                                    })
                                ] if pay_id else []
                            }
                            
                            try:
                                order_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'pos.order', 'create', [order_data])
                                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'pos.order', 'write', [[order_id], {'state': 'paid', 'pos_reference': pos_ref}])
                                logging.info(f"✅ VENTA EN ODOO [{st_name}] -> Ticket {serie}-{numero} | {litros:.2f}L | {total_eur:.2f}€ | Odoo ID: {order_id} | Ref: {pos_ref}")
                            except Exception as odoo_err:
                                logging.error(f"❌ Error al crear pedido [{st_name}] Ticket {serie}-{numero}: {odoo_err}")
                                
                            last_id = det_id
                            state[key] = last_id
                            save_state(state)
                except Exception as sales_err:
                    logging.error(f"Error procesando ventas de {st_name}: {sales_err}")
                    
            conn.close()
        except Exception as err:
            logging.error(f"Error en bucle global de captura: {err}")
            
        time.sleep(1)

if __name__ == "__main__":
    sync_loop()
