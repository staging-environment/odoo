#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo" << 'EOF'
SELECT id, name, bundle, path, directive FROM ir_asset WHERE path LIKE '%permission_matrix%' ORDER BY id;
EOF