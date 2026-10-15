#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    repsol = env['pos.config'].browse(7)
    c4 = env['res.company'].browse(4)

    # Dedicated Cash Journal for Repsol in C4
    j_cash = env['account.journal'].search([('company_id', '=', 4), ('code', '=', 'REPSC')], limit=1)
    if not j_cash:
        j_cash = env['account.journal'].create({
            'name': 'Efectivo E.S. Repsol',
            'type': 'cash',
            'company_id': 4,
            'code': 'REPSC',
        })
    pm_cash = env['pos.payment.method'].search([('company_id', '=', 4), ('journal_id', '=', j_cash.id)], limit=1)
    if not pm_cash:
        pm_cash = env['pos.payment.method'].create({
            'name': 'Efectivo E.S. Repsol',
            'company_id': 4,
            'journal_id': j_cash.id,
        })

    # Bank Payment Method for C4
    j_bank = env['account.journal'].search([('company_id', '=', 4), ('type', '=', 'bank')], limit=1)
    pm_bank = env['pos.payment.method'].search([('company_id', '=', 4), ('journal_id', '=', j_bank.id)], limit=1)
    if not pm_bank:
        pm_bank = env['pos.payment.method'].create({
            'name': 'Tarjeta Bancaria',
            'company_id': 4,
            'journal_id': j_bank.id,
        })

    # Picking type for C4
    pt = env['stock.picking.type'].search([('company_id', '=', 4), ('code', '=', 'outgoing')], limit=1)
    j_pos = env['account.journal'].search([('company_id', '=', 4), ('name', '=', 'Punto de venta')], limit=1)
    j_inv = env['account.journal'].search([('company_id', '=', 4), ('type', '=', 'sale')], limit=1)

    repsol.write({
        'company_id': 4,
        'journal_id': j_pos.id if j_pos else False,
        'invoice_journal_id': j_inv.id if j_inv else False,
        'payment_method_ids': [(6, 0, [pm_cash.id, pm_bank.id])],
        'picking_type_id': pt.id if pt else repsol.picking_type_id.id,
    })
    print("SUCCESS! E.S. Repsol is now under Company:", repsol.company_id.name, f"(ID: {repsol.company_id.id})")
    cr.commit()
EOF