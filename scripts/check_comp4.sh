#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    c4 = env['res.company'].browse(4)
    print("Company 4:", c4.name)
    journals = env['account.journal'].search([('company_id', '=', 4)])
    print("Journals in Comp 4:", [j.name for j in journals])
    warehouses = env['stock.warehouse'].search([('company_id', '=', 4)])
    print("Warehouses in Comp 4:", [w.name for w in warehouses])
    c3 = env['res.company'].browse(3)
    print("Company 3:", c3.name)
    journals3 = env['account.journal'].search([('company_id', '=', 3)])
    print("Journals in Comp 3:", [j.name for j in journals3])
EOF