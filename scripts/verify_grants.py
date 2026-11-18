import subprocess

def run_remote(cmd):
    full_cmd = ["ssh", "utrecar-dev", cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    return res.stdout.strip()

print("--- 1. Utrecar DBs ---")
print(run_remote("docker exec -i ddev-utrecar3-db mysql -udb -pdb -N -e \"SHOW GRANTS FOR 'read_utrecardbs'@'%';\""))

print("\n--- 2. Admin-Platform ---")
print(run_remote("docker exec -i ddev-admin-platform-db mysql -N -e \"SHOW GRANTS FOR 'read_adminplatform'@'%';\""))

print("\n--- 3. Windows Virtusgesnet ---")
print(run_remote("docker exec -i ddev-windows-virtusgesnet-db mysql -N -e \"SHOW GRANTS FOR 'read_winvirtus'@'%';\""))

print("\n--- 4. Status Utrecar ---")
print(run_remote("docker exec -i ddev-status-utrecar-db mysql -N -e \"SHOW GRANTS FOR 'read_statusutr'@'%';\""))

print("\n--- 5. Pre Admin-Platform ---")
print(run_remote("docker exec -i ddev-pre-admin-platform-db mysql -N -e \"SHOW GRANTS FOR 'read_preadmin'@'%';\""))

print("\n--- 6. Rentacar ES ---")
print(run_remote("docker exec -i ddev-rentacar-es-db mysql -N -e \"SHOW GRANTS FOR 'read_rentacar'@'%';\""))

print("\n--- 7. Odoo 17 ERP (PostgreSQL) ---")
print(run_remote("docker exec -i ddev-odoo-db psql -U db -d odoo -c \"SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE grantee='read_odoo' GROUP BY grantee, privilege_type;\""))
