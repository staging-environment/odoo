#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo" << 'EOF'
SELECT id, name, res_model FROM ir_act_window WHERE id IN (382, 390, 402, 397);
SELECT d.name as xml_id, d.res_id FROM ir_model_data d WHERE d.model = 'ir.actions.act_window' AND d.res_id IN (382, 390, 402, 397);
EOF