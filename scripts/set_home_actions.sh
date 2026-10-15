#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    home_action = env.ref('pos_gas_station.action_gas_station_dashboard', raise_if_not_found=False)
    print("Home Action ID:", home_action.id if home_action else None)

    all_companies = env['res.company'].search([])
    for u in env['res.users'].search([('active', '=', True)]):
        u.sudo().write({
            'action_id': home_action.id if home_action else False,
            'company_ids': [(6, 0, all_companies.ids)]
        })
        print(f"Set home action and companies for: {u.name} ({u.login})")
    cr.commit()
EOF