#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    users = env['res.users'].search([('active', 'in', [True, False])])
    print("ALL USERS:")
    for u in users:
        print(f"ID: {u.id} | Name: {u.name} | Login: {u.login} | Active: {u.active} | Groups: {[g.name for g in u.groups_id]}")
EOF