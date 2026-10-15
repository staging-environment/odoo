#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    s10 = env['pos.session'].browse(10)
    print("S10 state:", s10.state)
    if s10.state != 'closed':
        s10.action_pos_session_closing_control()
        print("S10 state after closing control:", s10.state)
        cr.commit()
EOF