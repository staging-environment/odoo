#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    sessions = env['pos.session'].search([('config_id', '=', 7)])
    for s in sessions:
        print(f"Session: {s.name} | State: {s.state} | Company: {s.company_id.name}")
EOF