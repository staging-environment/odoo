#!/bin/bash
ssh developer@164.68.101.69 << 'EOF'
docker exec ddev-odoo-odoo odoo -c /etc/odoo/odoo.conf -u web,pos_gas_station -d odoo --stop-after-init
docker exec -i -e PGPASSWORD=db ddev-odoo-odoo psql -h db -U db -d odoo -c "DELETE FROM ir_attachment WHERE url LIKE '%/assets/%';"
docker restart ddev-odoo-odoo
echo "WEB AND POS_GAS_STATION UPGRADED SUCCESSFULLY!"
EOF