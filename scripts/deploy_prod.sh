#!/bin/bash
set -e
echo "Conectando con utrecar-dev..."
ssh utrecar-dev << 'REMOTE_COMMANDS'
set -e
cd /home/developer/Projects/odoo
echo "=== 1. Git pull origin main ==="
git pull origin main
echo "=== 2. Limpieza de assets en DB ==="
docker exec ddev-odoo-db psql -U db -d db -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%' OR name LIKE '%assets%pos%';"
echo "=== 3. Reiniciando contenedor Odoo ==="
docker restart ddev-odoo-odoo
echo "=== Despliegue completado con éxito ==="
REMOTE_COMMANDS

