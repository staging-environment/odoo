#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    c1 = env['res.company'].browse(1)
    c4 = env['res.company'].browse(4)
    print("C1 chart_template:", c1.chart_template)
    try:
        env['account.chart.template'].try_loading(c1.chart_template, company=c4)
        print("Success loading chart template for C4!")
        cr.commit()
    except Exception as e:
        print("Error loading chart template:", e)
EOF