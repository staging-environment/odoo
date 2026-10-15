#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i ddev-odoo-odoo python3" << 'EOF'
import odoo
from odoo import api

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.registry('odoo').cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    companies = env['res.company'].search([])
    print("COMPANIES:")
    for c in companies:
        print(f"ID: {c.id} | Name: {c.name} | Partner: {c.partner_id.name if c.partner_id else None}")
    
    configs = env['pos.config'].search([])
    print("\nPOS CONFIGS / STATIONS:")
    for cfg in configs:
        print(f"ID: {cfg.id} | Name: {cfg.name} | Company: {cfg.company_id.name} (ID: {cfg.company_id.id})")
EOF