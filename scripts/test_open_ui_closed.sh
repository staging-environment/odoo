#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    repsol = env['pos.config'].browse(7)
    print("Testing repsol.open_ui() with closed sessions...")
    try:
        action = repsol.open_ui()
        print("open_ui action:", action)
        # Check if session was created:
        session = env['pos.session'].search([('config_id', '=', 7), ('state', '!=', 'closed')], limit=1)
        print("Created session:", session.name if session else "NONE", session.state if session else None)
    except Exception as e:
        print("Error during open_ui:", e)
EOF