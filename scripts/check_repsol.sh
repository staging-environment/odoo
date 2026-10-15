#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    repsol = env['pos.config'].browse(7)
    print("REPSOL FIELDS:")
    print("Name:", repsol.name)
    print("Company:", repsol.company_id.name, repsol.company_id.id)
    print("Journal:", repsol.journal_id.name if repsol.journal_id else None, repsol.journal_id.company_id.name if repsol.journal_id else None)
    print("Invoice Journal:", repsol.invoice_journal_id.name if repsol.invoice_journal_id else None)
    print("Payment Methods:", [(pm.name, pm.company_id.name if pm.company_id else None) for pm in repsol.payment_method_ids])
    print("Picking Type:", repsol.picking_type_id.name if repsol.picking_type_id else None, repsol.picking_type_id.company_id.name if repsol.picking_type_id else None)
EOF