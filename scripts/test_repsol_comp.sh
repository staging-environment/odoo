#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    c4 = env['res.company'].browse(4)
    repsol = env['pos.config'].browse(7)
    try:
        repsol.write({'company_id': c4.id})
        print("Success setting company 4!")
    except Exception as e:
        print("Write error:", e)
    cr.rollback()
EOF