#!/bin/bash
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo" << 'EOF'
SELECT id, name, url, create_date, write_date FROM ir_attachment WHERE url LIKE '%assets%' LIMIT 10;
EOF