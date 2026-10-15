#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    sessions = env['pos.session'].search([('config_id', '=', 7)])
    print("SESSIONS FOR REPSOL:")
    for s in sessions:
        print(f"ID: {s.id} | Name: {s.name} | State: {s.state} | Orders: {len(s.order_ids)}")
EOF