#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    pms = env['pos.payment.method'].search([])
    for pm in pms:
        print(f"PM: {pm.name} | Comp: {pm.company_id.name if pm.company_id else 'GLOBAL'}")
EOF