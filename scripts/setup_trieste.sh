#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    c4 = env['res.company'].browse(4)
    print("Renaming Company 4 to 'A.R. Trieste'...")
    c4.write({'name': 'A.R. Trieste'})
    if c4.partner_id:
        c4.partner_id.write({'name': 'A.R. Trieste'})
    
    # Check warehouse for company 4
    wh = env['stock.warehouse'].search([('company_id', '=', 4)], limit=1)
    print("Warehouse for C4:", wh.name if wh else "None")
    pt = env['stock.picking.type'].search([('company_id', '=', 4), ('code', '=', 'outgoing')], limit=1)
    if not pt and wh:
        pt = wh.out_type_id
    print("Picking type for C4:", pt.name if pt else "None")

    # Check or create account journal for company 4
    # Check chart of accounts on company 4
    print("C4 chart_template:", c4.chart_template)
    cr.commit()
EOF