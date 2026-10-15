#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    repsol = env['pos.config'].browse(7)
    print("Testing open_ui with company 4 context:")
    try:
        repsol_c4 = repsol.with_company(repsol.company_id)
        action = repsol_c4.open_ui()
        print("Action:", action)
        session = env['pos.session'].search([('config_id', '=', 7), ('state', '!=', 'closed')], limit=1)
        print("Open session:", session.name, session.state, "Company:", session.company_id.name)
    except Exception as e:
        print("Error:", e)
EOF