#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo" << 'EOF'
SELECT m.id, m.name, d.name as xml_id, m.action FROM ir_ui_menu m JOIN ir_model_data d ON d.res_id = m.id AND d.model = 'ir.ui.menu' WHERE d.module = 'point_of_sale';
EOF