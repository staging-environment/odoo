#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    david = env['res.users'].browse(8)
    print("David's groups:")
    for g in david.groups_id:
        xml_ids = g.get_external_id().get(g.id)
        print(f"Group ID: {g.id} | Name: {g.name} | Category: {g.category_id.name if g.category_id else None} | XMLID: {xml_ids}")
EOF