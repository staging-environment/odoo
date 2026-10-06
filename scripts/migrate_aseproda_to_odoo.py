#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
MIGRACIÓN E INTEGRACIÓN DE CLIENTES Y FACTURACIÓN ASEPRODA ➔ ODOO CLOUD
=============================================================================
Entorno: Producción Utrecar
Origen: MariaDB / MySQL 5.5 (virtusgesnet) en 164.68.101.69:33061
Destino: Odoo 17 Cloud (https://odoo.utrecar.com)

Modelos Odoo afectados:
  - res.partner (Clientes y contactos)
  - res.partner.bank (Cuentas bancarias de clientes)
  - account.move & account.move.line (Facturación oficial y abonos)
=============================================================================
"""

import sys
import os
import argparse
import logging
import pymysql
import xmlrpc.client
from collections import defaultdict
from datetime import datetime

# --- CONFIGURACIÓN CONEXIONES ---
DB_HOST = os.getenv("ASEPRODA_DB_HOST", "164.68.101.69")
DB_PORT = int(os.getenv("ASEPRODA_DB_PORT", "33061"))
DB_USER = os.getenv("ASEPRODA_DB_USER", "root")
DB_PASS = os.getenv("ASEPRODA_DB_PASS", ".root.")
DB_NAME = "virtusgesnet"

ODOO_URL = os.getenv("ODOO_URL", "https://odoo.utrecar.com")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "jarodriguezbonilla@gmail.com")
ODOO_PASS = os.getenv("ODOO_PASS", "Utrecar2026!")

TAX_MAP = {
    21.0: 4,
    10.0: 5,
    4.0: 6,
    0.0: 3
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def get_odoo_client():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    if not uid:
        raise ConnectionError(f"No se pudo autenticar en Odoo con el usuario {ODOO_USER}")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def get_mariadb_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def sync_clients(uid, models):
    logging.info("🚀 Iniciando sincronización de clientes Aseproda ➔ Odoo...")
    
    # 1. Geografía Odoo
    spain = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.country', 'search_read', [[('code', '=', 'ES')]], {'fields': ['id']})
    spain_id = spain[0]['id'] if spain else 68
    
    states = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.country.state', 'search_read', [[('country_id', '=', spain_id)]], {'fields': ['id', 'name', 'code']})
    state_map_by_name = {s['name'].lower(): s['id'] for s in states}
    state_map_by_code = {s['code']: s['id'] for s in states}
    
    cp_to_code = {
        '01': 'VI', '02': 'AB', '03': 'A', '04': 'AL', '05': 'AV', '06': 'BA', '07': 'PM', '08': 'B', '09': 'BU', '10': 'CC',
        '11': 'CA', '12': 'CS', '13': 'CR', '14': 'CO', '15': 'C', '16': 'CU', '17': 'GI', '18': 'GR', '19': 'GU', '20': 'SS',
        '21': 'H', '22': 'HU', '23': 'J', '24': 'LE', '25': 'L', '26': 'LO', '27': 'LU', '28': 'M', '29': 'MA', '30': 'MU',
        '31': 'NA', '32': 'OR', '33': 'O', '34': 'P', '35': 'GC', '36': 'PO', '37': 'SA', '38': 'TF', '39': 'S', '40': 'SG',
        '41': 'SE', '42': 'SO', '43': 'T', '44': 'TE', '45': 'TO', '46': 'V', '47': 'VA', '48': 'BI', '49': 'ZA', '50': 'Z',
        '51': 'CE', '52': 'ML'
    }
    
    def resolve_state(provincia, cp):
        if provincia:
            p_clean = provincia.strip().lower()
            if p_clean in state_map_by_name:
                return state_map_by_name[p_clean]
            for name, sid in state_map_by_name.items():
                if name in p_clean or p_clean in name:
                    return sid
        if cp and len(cp) >= 2:
            prefix = cp[:2]
            if prefix in cp_to_code:
                code = cp_to_code[prefix]
                return state_map_by_code.get(code)
        return False

    # 2. Índice actual Odoo
    existing_partners = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search_read',
        [[('active', 'in', [True, False])]],
        {'fields': ['id', 'ref', 'vat', 'name']}
    )
    partner_by_ref = {p['ref']: p['id'] for p in existing_partners if p['ref']}
    partner_by_vat = {p['vat']: p['id'] for p in existing_partners if p['vat']}
    logging.info(f"✅ Índice de partners en Odoo: {len(existing_partners)} registros")

    # 3. Leer clientes de MariaDB
    conn = get_mariadb_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM clientes ORDER BY Codigo ASC")
        clients = cur.fetchall()
    conn.close()
    
    total = len(clients)
    logging.info(f"📊 Total clientes Aseproda a procesar: {total}")

    created = 0
    updated = 0
    errors = 0

    for idx, c in enumerate(clients, 1):
        codigo = c['Codigo']
        ref = f"ASEPRODA-{codigo}"
        nif = (c['NIF'] or "").strip().upper()
        name = (c['Nombre'] or "").strip() or f"Cliente {codigo}"
        cp = (c['DPFiscal'] or "").strip()
        provincia = (c['ProvinciaFiscal'] or "").strip()
        state_id = resolve_state(provincia, cp)

        vat = False
        if nif:
            if len(nif) >= 8 and not nif[:2].isalpha():
                vat = f"ES{nif}"
            elif len(nif) >= 9 and nif[:2].isalpha():
                vat = nif
            else:
                vat = f"ES{nif}"

        is_company = bool(nif and nif[0] in "ABCDEFGHJPRSUVNW")

        comment_parts = [f"Código Aseproda: {codigo}"]
        if c.get('CodigoDeFormaDePagoHabitual'):
            comment_parts.append(f"Forma de Pago: {c['CodigoDeFormaDePagoHabitual']}")
        if c.get('PeriodoDeFacturacion'):
            comment_parts.append(f"Periodo Facturación: {c['PeriodoDeFacturacion']}")
        if c.get('CreditoMaximoDelPeriodo'):
            comment_parts.append(f"Crédito Máximo: {c['CreditoMaximoDelPeriodo']} €")
        if c.get('Notas'):
            comment_parts.append(f"Notas: {c['Notas']}")
        if c.get('Avisos'):
            comment_parts.append(f"Avisos: {c['Avisos']}")

        vals = {
            'name': name,
            'ref': ref,
            'street': (c['DomicilioFiscal'] or "").strip() or False,
            'city': (c['PoblacionFiscal'] or "").strip() or False,
            'zip': cp or False,
            'state_id': state_id,
            'country_id': spain_id,
            'phone': (c['Telefono'] or "").strip() or False,
            'email': (c['EMail'] or "").strip() or False,
            'website': (c['Web'] or "").strip() or False,
            'customer_rank': 1,
            'is_company': is_company,
            'company_type': 'company' if is_company else 'person',
            'active': False if c['EnBaja'] == 1 else True,
            'comment': "\n".join(comment_parts)
        }
        if vat:
            vals['vat'] = vat

        partner_id = partner_by_ref.get(ref) or (partner_by_vat.get(vat) if vat else None)

        try:
            if partner_id:
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'write', [[partner_id], vals])
                updated += 1
            else:
                partner_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'create', [vals])
                partner_by_ref[ref] = partner_id
                if vat:
                    partner_by_vat[vat] = partner_id
                created += 1

            iban = (c['IBAN'] or "").strip().replace(" ", "").upper()
            if iban and len(iban) >= 15 and partner_id:
                bank_exists = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner.bank', 'search', [[('acc_number', '=', iban), ('partner_id', '=', partner_id)]])
                if not bank_exists:
                    try:
                        models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner.bank', 'create', [{
                            'acc_number': iban,
                            'partner_id': partner_id,
                            'bank_name': (c['NombreDeEntidadFinanciera'] or "").strip() or False
                        }])
                    except Exception:
                        pass

        except Exception as e:
            errors += 1
            logging.error(f"Error en cliente {codigo}: {e}")

        if idx % 200 == 0 or idx == total:
            logging.info(f"Progreso Clientes: {idx}/{total} ({(idx/total)*100:.1f}%) | Creados: {created} | Actualizados: {updated}")

    logging.info(f"✅ Sincronización de clientes completada: {created} creados, {updated} actualizados, {errors} errores.")
    return partner_by_ref

def sync_invoices(uid, models, year=2026, limit=None):
    logging.info(f"🚀 Iniciando sincronización de facturación Aseproda (Año {year}) ➔ Odoo...")

    # 1. Mapeo de clientes
    partners = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search_read',
        [[('active', 'in', [True, False])]],
        {'fields': ['id', 'ref', 'vat']}
    )
    partner_by_ref = {p['ref']: p['id'] for p in partners if p['ref']}
    partner_by_vat = {p['vat']: p['id'] for p in partners if p['vat']}
    logging.info(f"✅ {len(partner_by_ref)} clientes indexados en Odoo")

    # 2. Mapeo de productos
    products = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'product.product', 'search_read',
        [[]],
        {'fields': ['id', 'default_code', 'name']}
    )
    product_by_code = {str(p['default_code']): p['id'] for p in products if p['default_code']}
    default_prod_id = product_by_code.get('1') or products[0]['id']
    logging.info(f"✅ {len(product_by_code)} productos indexados en Odoo")

    # 3. Comprobar facturas ya existentes en Odoo
    existing_moves = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'account.move', 'search_read',
        [[('move_type', 'in', ['out_invoice', 'out_refund']), ('invoice_date', '>=', f'{year}-01-01')]],
        {'fields': ['id', 'ref', 'payment_reference']}
    )
    existing_invoices = set()
    for m in existing_moves:
        if m.get('ref'):
            existing_invoices.add(m['ref'])
        if m.get('payment_reference'):
            existing_invoices.add(m['payment_reference'])
    logging.info(f"✅ Facturas Odoo ya existentes en {year}: {len(existing_invoices)}")

    # 4. Consultar facturas de Aseproda y PRECARGAR todas sus líneas en una sola consulta
    conn = get_mariadb_connection()
    with conn.cursor() as cur:
        query = f"""
            SELECT Serie, Numero, CodigoDeCliente, FechaYHora, ImporteBruto, ImporteDeIVA, ImporteTotal, Nombre, NIF
            FROM facturasyticketsdeventa
            WHERE EsTicket = 0 AND CodigoDeCliente > 0 AND YEAR(FechaYHora) = {year}
            ORDER BY FechaYHora ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query)
        invoices = cur.fetchall()

        # Precargar líneas de forma ultrarrápida
        logging.info("Precargando líneas de factura en bloque...")
        cur.execute(f"""
            SELECT d.Serie, d.Numero, d.CodigoDeProducto, d.Cantidad, d.Precio, d.Importe, d.PorcentajeDeIva
            FROM detalledefacturasyticketsdeventa d
            JOIN facturasyticketsdeventa f 
              ON d.CodigoDeEmpresaPropia = f.CodigoDeEmpresaPropia 
             AND d.Serie = f.Serie 
             AND d.Numero = f.Numero
            WHERE f.EsTicket = 0 AND f.CodigoDeCliente > 0 AND YEAR(f.FechaYHora) = {year}
            ORDER BY d.Serie, d.Numero, d.Orden ASC
        """)
        all_lines = cur.fetchall()
        lines_by_doc = defaultdict(list)
        for l in all_lines:
            lines_by_doc[(l['Serie'], l['Numero'])].append(l)
        logging.info(f"✅ Precargadas {len(all_lines)} líneas agrupadas en {len(lines_by_doc)} documentos.")

    conn.close()

    total_inv = len(invoices)
    logging.info(f"📊 Facturas Aseproda a procesar para {year}: {total_inv}")

    created = 0
    skipped = 0
    errors = 0

    for idx, inv in enumerate(invoices, 1):
        serie = inv['Serie']
        numero = inv['Numero']
        ref_doc = f"{serie}/{numero}"

        if ref_doc in existing_invoices:
            skipped += 1
            continue

        cliente_codigo = inv['CodigoDeCliente']
        ref_cliente = f"ASEPRODA-{cliente_codigo}"
        partner_id = partner_by_ref.get(ref_cliente)

        if not partner_id:
            nif = (inv['NIF'] or "").strip().upper()
            if nif:
                vat_search = f"ES{nif}" if len(nif) >= 8 and not nif[:2].isalpha() else nif
                partner_id = partner_by_vat.get(vat_search)

        if not partner_id:
            logging.warning(f"⚠️ Cliente no encontrado para factura {ref_doc} (Cod: {cliente_codigo}, NIF: {inv['NIF']})")
            errors += 1
            continue

        fecha_dt = inv['FechaYHora'] or datetime.now()
        fecha_str = fecha_dt.strftime('%Y-%m-%d')
        total_eur = float(inv['ImporteTotal'] or 0.0)
        is_refund = total_eur < 0

        # Obtener líneas desde la memoria local instantánea
        detalles = lines_by_doc.get((serie, numero), [])

        invoice_lines = []
        if detalles:
            for d in detalles:
                prod_code = str(d['CodigoDeProducto'])
                p_id = product_by_code.get(prod_code, default_prod_id)
                qty = abs(float(d['Cantidad'] or 1.0))
                subtotal_eur = abs(float(d['Importe'] or 0.0))
                iva_pct = float(d['PorcentajeDeIva'] or 21.0)
                tax_id = TAX_MAP.get(iva_pct, 4)

                unit_price = round(subtotal_eur / qty, 4) if qty > 0 else subtotal_eur

                invoice_lines.append((0, 0, {
                    'product_id': p_id,
                    'quantity': qty,
                    'price_unit': unit_price,
                    'tax_ids': [(6, 0, [tax_id])],
                    'name': f"Ref. {prod_code} | Factura {ref_doc}"
                }))
        else:
            iva_imp = float(inv['ImporteDeIVA'] or 0.0)
            base_imp = abs(total_eur - iva_imp)
            invoice_lines.append((0, 0, {
                'product_id': default_prod_id,
                'quantity': 1.0,
                'price_unit': base_imp,
                'tax_ids': [(6, 0, [4])],
                'name': f"Suministro Carburante / Servicios - Factura {ref_doc}"
            }))

        move_vals = {
            'move_type': 'out_refund' if is_refund else 'out_invoice',
            'partner_id': partner_id,
            'invoice_date': fecha_str,
            'date': fecha_str,
            'payment_reference': ref_doc,
            'ref': ref_doc,
            'invoice_line_ids': invoice_lines
        }

        try:
            move_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'create', [move_vals])
            models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'action_post', [[move_id]])
            created += 1
            existing_invoices.add(ref_doc)
        except Exception as e:
            errors += 1
            logging.error(f"Error creando factura {ref_doc}: {e}")

        if idx % 100 == 0 or idx == total_inv:
            logging.info(f"Progreso Facturas {year}: {idx}/{total_inv} ({(idx/total_inv)*100:.1f}%) | Creadas: {created} | Saltadas: {skipped} | Errores: {errors}")

    logging.info(f"✅ Sincronización de facturas {year} completada: {created} creadas, {skipped} saltadas, {errors} errores.")

def main():
    parser = argparse.ArgumentParser(description="Migración Aseproda ➔ Odoo Cloud")
    parser.add_argument("--clients", action="store_true", help="Sincronizar clientes")
    parser.add_argument("--invoices", action="store_true", help="Sincronizar facturas")
    parser.add_argument("--year", type=int, default=2026, help="Año de facturación a sincronizar (defecto: 2026)")
    parser.add_argument("--limit", type=int, default=None, help="Límite de registros para pruebas")
    parser.add_argument("--all", action="store_true", help="Sincronizar clientes y facturas del año indicado")
    args = parser.parse_args()

    uid, models = get_odoo_client()
    logging.info(f"✅ Conectado exitosamente a Odoo Cloud ({ODOO_URL}) con UID {uid}")

    if args.all or (not args.clients and not args.invoices):
        sync_clients(uid, models)
        sync_invoices(uid, models, year=args.year, limit=args.limit)
    else:
        if args.clients:
            sync_clients(uid, models)
        if args.invoices:
            sync_invoices(uid, models, year=args.year, limit=args.limit)

if __name__ == "__main__":
    main()
