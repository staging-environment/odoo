#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    env['utrecar.role'].auto_link_admin_users()
    cr.commit()
    ceo = env['utrecar.role'].search([('code', '=', 'ceo')], limit=1)
    print("CEO user count:", ceo.user_count)
    print("CEO users:", [(u.id, u.name, u.login) for u in ceo.user_ids])
EOF