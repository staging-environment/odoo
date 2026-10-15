#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    for uid in [2, 8]:
        u = env['res.users'].browse(uid)
        print(f"User: {u.name} ({u.login}) | Main Company: {u.company_id.name} | Allowed Companies: {[c.name for c in u.company_ids]}")
EOF