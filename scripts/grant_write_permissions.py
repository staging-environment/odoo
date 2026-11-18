import subprocess

def run_remote(cmd):
    full_cmd = ["ssh", "utrecar-dev", cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR executing: {cmd}\nSTDERR: {res.stderr}")
    return res.stdout.strip()

print("--- 1. Utrecar DBs (Históricas) (MySQL 5.5) ---")
sql_utrecar3 = """
GRANT ALL PRIVILEGES ON virtusgesnet.* TO 'read_utrecardbs'@'%';
GRANT ALL PRIVILEGES ON administracioncorporativa.* TO 'read_utrecardbs'@'%';
GRANT ALL PRIVILEGES ON sii.* TO 'read_utrecardbs'@'%';
GRANT ALL PRIVILEGES ON pre_virtusgesnet.* TO 'read_utrecardbs'@'%';
GRANT ALL PRIVILEGES ON pre_administracioncorporativa.* TO 'read_utrecardbs'@'%';
GRANT ALL PRIVILEGES ON pre_sii.* TO 'read_utrecardbs'@'%';
GRANT ALL PRIVILEGES ON db.* TO 'read_utrecardbs'@'%';
FLUSH PRIVILEGES;
"""
print(run_remote(f"docker exec -i ddev-utrecar3-db mysql -udb -pdb -e \"{sql_utrecar3}\""))
print("Grants virtusgesnet:")
print(run_remote("docker exec -i ddev-utrecar3-db mysql -udb -pdb -N -e \"SHOW GRANTS FOR 'read_utrecardbs'@'%';\""))

print("\n--- 2. Admin-Platform (MariaDB 10.11) ---")
sql_admin = """
GRANT ALL PRIVILEGES ON db.* TO 'read_adminplatform'@'%';
GRANT ALL PRIVILEGES ON utrecar_ftp.* TO 'read_adminplatform'@'%';
FLUSH PRIVILEGES;
"""
print(run_remote(f"docker exec -i ddev-admin-platform-db mysql -e \"{sql_admin}\""))
print("Grants adminplatform:")
print(run_remote("docker exec -i ddev-admin-platform-db mysql -N -e \"SHOW GRANTS FOR 'read_adminplatform'@'%';\""))

print("\n--- 3. Windows Virtusgesnet (MariaDB 11.8) ---")
sql_win = """
GRANT ALL PRIVILEGES ON db.* TO 'read_winvirtus'@'%';
FLUSH PRIVILEGES;
"""
print(run_remote(f"docker exec -i ddev-windows-virtusgesnet-db mysql -e \"{sql_win}\""))
print("Grants winvirtus:")
print(run_remote("docker exec -i ddev-windows-virtusgesnet-db mysql -N -e \"SHOW GRANTS FOR 'read_winvirtus'@'%';\""))

print("\n--- 4. Status Utrecar (MariaDB 10.11) ---")
sql_status = """
GRANT ALL PRIVILEGES ON db.* TO 'read_statusutr'@'%';
FLUSH PRIVILEGES;
"""
print(run_remote(f"docker exec -i ddev-status-utrecar-db mysql -e \"{sql_status}\""))
print("Grants statusutr:")
print(run_remote("docker exec -i ddev-status-utrecar-db mysql -N -e \"SHOW GRANTS FOR 'read_statusutr'@'%';\""))

print("\n--- 5. Rentacar ES (MariaDB 11.8) ---")
sql_rent = """
GRANT ALL PRIVILEGES ON db.* TO 'read_rentacar'@'%';
FLUSH PRIVILEGES;
"""
print(run_remote(f"docker exec -i ddev-rentacar-es-db mysql -e \"{sql_rent}\""))
print("Grants rentacar:")
print(run_remote("docker exec -i ddev-rentacar-es-db mysql -N -e \"SHOW GRANTS FOR 'read_rentacar'@'%';\""))

print("\n--- 6. Pre Admin-Platform (MariaDB 10.11) ---")
sql_pre = """
CREATE USER IF NOT EXISTS 'read_preadmin'@'%' IDENTIFIED BY 'Pre#PlatRead_2026!v4';
GRANT ALL PRIVILEGES ON db.* TO 'read_preadmin'@'%';
FLUSH PRIVILEGES;
"""
print(run_remote(f"docker exec -i ddev-pre-admin-platform-db mysql -e \"{sql_pre}\""))
print("Grants preadmin:")
print(run_remote("docker exec -i ddev-pre-admin-platform-db mysql -N -e \"SHOW GRANTS FOR 'read_preadmin'@'%';\""))

print("\n--- 7. Odoo 17 ERP (PostgreSQL 15) ---")
sql_odoo = """
GRANT ALL PRIVILEGES ON DATABASE odoo TO read_odoo;
GRANT ALL ON SCHEMA public TO read_odoo;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO read_odoo;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO read_odoo;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO read_odoo;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO read_odoo;
"""
print(run_remote(f"docker exec -i ddev-odoo-db psql -U db -d odoo -c \"{sql_odoo}\""))
