#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo" << 'EOF'
SELECT id, name, key, type FROM ir_ui_view WHERE arch_db::text LIKE '%UtrecarPermissionMatrix%';
EOF