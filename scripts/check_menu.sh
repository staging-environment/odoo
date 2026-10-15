#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    m = env.ref('pos_gas_station.menu_utrecar_permission_root', raise_if_not_found=False)
    print("Menu Root:", m, m.name if m else None, "Parent:", m.parent_id if m else None, "Groups:", [g.name for g in m.groups_id] if m else None)
    # Check what user 2 can see in menus
    user2 = env['res.users'].browse(2)
    menus = env['ir.ui.menu'].with_user(user2).search([('parent_id', '=', False)])
    print("User 2 Root Menus:", [menu.name for menu in menus])
EOF