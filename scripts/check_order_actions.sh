#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo" << 'EOF'
SELECT id, name, module, res_id FROM ir_model_data WHERE module = 'point_of_sale' AND name LIKE '%order%' AND name LIKE '%action%';
EOF