#!/bin/bash
set -e

echo "=== PULLING LATEST CODE ON PRODUCTION ==="
ssh utrecar-dev "cd /home/developer/Projects/odoo && git pull origin main"

echo "=== PURGING CACHED WEB ASSETS IN DATABASE ==="
ssh utrecar-dev "docker exec -i ddev-odoo-db psql -U db -d odoo -c \"DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';\""

echo "=== UPGRADING pos_gas_station MODULE ==="
ssh utrecar-dev "docker exec -i ddev-odoo-odoo odoo -u pos_gas_station -d odoo --stop-after-init"

echo "=== RESTARTING ODOO CONTAINER ==="
ssh utrecar-dev "docker restart ddev-odoo-odoo"

echo "=== WAITING FOR ODOO TO BE READY ==="
sleep 4
ssh utrecar-dev "docker logs --tail 20 ddev-odoo-odoo"
echo "=== DEPLOYMENT COMPLETE ==="
