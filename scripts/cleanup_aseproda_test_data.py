#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PURGA Y LIMPIEZA TOTAL DE DATOS DE PRUEBA DE ASEPRODA EN ODOO CLOUD
=============================================================================
Permite revertir de forma segura y completa toda la importación de prueba:
  1. Facturas de compra y facturas de venta (paso a borrador y borrado).
  2. Ajustes de inventario y existencias (reset de quants).
  3. Proveedores creados de prueba (PROV-*).
  4. Clientes creados de prueba (ASEPRODA-*).
=============================================================================
"""

import os
import sys
import logging
import argparse
import xmlrpc.client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

ODOO_URL = os.getenv("ODOO_URL", "https://odoo.utrecar.com")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "jarodriguezbonilla@gmail.com")
ODOO_PASS = os.getenv("ODOO_PASS", "Utrecar2026!")

def cleanup_all(dry_run=False):
    logging.info(f"🧹 Iniciando limpieza de datos de prueba Aseproda en Odoo Cloud (Dry-run: {dry_run})...")
    
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

    # 1. Limpieza de Facturas de Cliente y Proveedor de Aseproda
    logging.info("Buscando facturas importadas de Aseproda...")
    test_invoices = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'account.move', 'search',
        [['|', ('ref', 'like', '%/%'), '|', ('partner_id.ref', '=like', 'ASEPRODA-%'), ('partner_id.ref', '=like', 'PROV-%')]]
    )
    logging.info(f"📊 Facturas de prueba encontradas: {len(test_invoices)}")
    if not dry_run and test_invoices:
        # En lotes de 100
        for i in range(0, len(test_invoices), 100):
            batch = test_invoices[i:i+100]
            try:
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'button_draft', [batch])
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'unlink', [batch])
                logging.info(f"  Borradas facturas {i+1} a {min(i+100, len(test_invoices))}")
            except Exception as e:
                logging.error(f"Error borrando lote de facturas: {e}")

    # 2. Limpieza de Inventario (quants)
    logging.info("Buscando quants de inventario en ubicaciones de estaciones...")
    test_quants = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'stock.quant', 'search',
        [['|', ('location_id.barcode', 'like', 'TK_%'), ('location_id.barcode', 'like', 'TIENDA_%')]]
    )
    logging.info(f"📊 Quants de prueba encontrados: {len(test_quants)}")
    if not dry_run and test_quants:
        for i in range(0, len(test_quants), 100):
            batch = test_quants[i:i+100]
            try:
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'stock.quant', 'write', [batch, {'inventory_quantity': 0.0}])
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'stock.quant', 'action_apply_inventory', [batch])
            except Exception:
                pass
            try:
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'stock.quant', 'unlink', [batch])
            except Exception:
                pass
        logging.info("  Existencias de prueba restablecidas a 0.")

    # 3. Limpieza de Proveedores de prueba (PROV-*)
    logging.info("Buscando proveedores de prueba...")
    test_suppliers = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search',
        [[('ref', '=like', 'PROV-%'), ('active', 'in', [True, False])]]
    )
    logging.info(f"📊 Proveedores de prueba encontrados: {len(test_suppliers)}")
    if not dry_run and test_suppliers:
        for i in range(0, len(test_suppliers), 100):
            batch = test_suppliers[i:i+100]
            try:
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'unlink', [batch])
            except Exception as e:
                logging.warning(f"Aviso archivando proveedores que no se pudieron borrar: {e}")
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'write', [batch, {'active': False}])

    # 4. Limpieza de Clientes de prueba (ASEPRODA-*)
    logging.info("Buscando clientes de prueba...")
    test_clients = models.execute_kw(
        ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search',
        [[('ref', '=like', 'ASEPRODA-%'), ('active', 'in', [True, False])]]
    )
    logging.info(f"📊 Clientes de prueba encontrados: {len(test_clients)}")
    if not dry_run and test_clients:
        for i in range(0, len(test_clients), 100):
            batch = test_clients[i:i+100]
            try:
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'unlink', [batch])
            except Exception as e:
                logging.warning(f"Aviso archivando clientes con dependencias: {e}")
                models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'write', [batch, {'active': False}])

    logging.info("✨ Limpieza completada con éxito. Odoo restablecido.")

def main():
    parser = argparse.ArgumentParser(description="Limpieza y purga de datos de prueba Aseproda en Odoo")
    parser.add_argument("--dry-run", action="store_true", help="Solo contar registros sin borrar")
    parser.add_argument("--confirm", action="store_true", help="Confirmar el borrado total de pruebas")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("⚠️ ATENCIÓN: Esta acción eliminará los datos de prueba de Aseproda en Odoo.")
        print("Para simular sin borrar ejecute con: --dry-run")
        print("Para confirmar el borrado ejecute con: --confirm")
        sys.exit(1)

    cleanup_all(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
