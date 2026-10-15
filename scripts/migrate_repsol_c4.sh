#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    repsol = env['pos.config'].browse(7)
    c4 = env['res.company'].browse(4)
    print("Migrating E.S. Repsol to company A.R. Trieste (ID: 4)...")

    # Payment methods for C4
    pm_cash = env['pos.payment.method'].search([('company_id', '=', 4), ('name', 'ilike', 'efectivo')], limit=1)
    if not pm_cash:
        pm_cash = env['pos.payment.method'].create({
            'name': 'Efectivo E.S. Repsol',
            'company_id': 4,
            'journal_id': 22,
        })
    pm_bank = env['pos.payment.method'].search([('company_id', '=', 4), ('name', 'ilike', 'tarjeta')], limit=1)
    if not pm_bank:
        pm_bank = env['pos.payment.method'].create({
            'name': 'Tarjeta Bancaria',
            'company_id': 4,
            'journal_id': 21,
        })

    # Picking type for C4
    wh = env['stock.warehouse'].search([('company_id', '=', 4)], limit=1)
    pt = env['stock.picking.type'].search([('company_id', '=', 4), ('code', '=', 'outgoing')], limit=1)

    repsol.write({
        'company_id': 4,
        'journal_id': 24,
        'invoice_journal_id': 16,
        'payment_method_ids': [(6, 0, [pm_cash.id, pm_bank.id])],
        'picking_type_id': pt.id if pt else repsol.picking_type_id.id,
    })
    print("Repsol migrated successfully! New Company:", repsol.company_id.name)
    cr.commit()
EOF