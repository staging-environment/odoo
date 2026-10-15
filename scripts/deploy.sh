#!/bin/bash
set -e
echo "1. Pulling latest code on server..."
ssh developer@164.68.101.69 "cd /home/developer/Projects/odoo && git pull"

echo "2. Upgrading pos_gas_station module..."
ssh developer@164.68.101.69 "docker exec ddev-odoo-odoo odoo -c /etc/odoo/odoo.conf -u pos_gas_station -d odoo --stop-after-init"

echo "3. Purging web asset bundle cache..."
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo -c \"DELETE FROM ir_attachment WHERE url LIKE '%/assets/%';\""

echo "4. Restarting ddev-odoo-odoo container..."
ssh developer@164.68.101.69 "docker restart ddev-odoo-odoo"

echo "5. Verifying CEO role users..."
ssh developer@164.68.101.69 "docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo -c \"SELECT r.name as role_name, count(u.id) as user_count FROM utrecar_role r LEFT JOIN res_users u ON u.utrecar_role_id = r.id GROUP BY r.id, r.name;\""

echo "ALL DEPLOYMENT STEPS FINISHED SUCCESSFULLY!"