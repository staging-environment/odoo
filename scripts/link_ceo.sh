#!/bin/bash
set -e
echo "Executing Python script in Odoo to auto-link CEO admins and sync groups..."
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    ceo = env['utrecar.role'].search([('code', '=', 'ceo')], limit=1)
    admin_group = env.ref('base.group_system', raise_if_not_found=False)
    print("CEO Role ID:", ceo.id if ceo else None)
    print("Admin Group ID:", admin_group.id if admin_group else None)

    if ceo and admin_group:
        admins = env['res.users'].search([
            ('groups_id', 'in', [admin_group.id]),
            ('active', '=', True)
        ])
        print("Found Admins:", [(u.id, u.name, u.login) for u in admins])
        for adm in admins:
            adm.sudo().write({'utrecar_role_id': ceo.id})
            adm._sync_utrecar_role_groups()
            print(f"Assigned CEO role to: {adm.name} ({adm.login})")
        cr.commit()

    all_roles = env['utrecar.role'].search([])
    for r in all_roles:
        print(f"Role: {r.name} | Users: {len(r.user_ids)} -> {[u.name for u in r.user_ids]}")
EOF
echo "Auto-link completed!"