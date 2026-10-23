#!/usr/bin/env bash
set -euo pipefail

# Asegurar grupo docker si la sesión actual aún no ha refrescado
if ! docker ps >/dev/null 2>&1; then
    exec sg docker -c "$0 $*"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DUMP_FILE="$PROJECT_DIR/scratch/odoo_prod.sql.gz"
FILESTORE_FILE="$PROJECT_DIR/scratch/odoo_filestore.tar.gz"

echo "============================================="
echo " Restaurando entorno de Producción en Local  "
echo "============================================="

cd "$PROJECT_DIR"

if [ ! -f "$DUMP_FILE" ]; then
    echo "❌ Error: No se encuentra $DUMP_FILE"
    exit 1
fi

echo "[1/4] Arrancando DDEV local..."
ddev start

echo "[2/4] Preparando base de datos 'odoo' en Postgres local..."
ddev exec -s db "psql -U db -d db -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'odoo' AND pid <> pg_backend_pid();\"" || true
ddev exec -s db "psql -U db -d db -c \"DROP DATABASE IF EXISTS odoo;\""
ddev exec -s db "psql -U db -d db -c \"CREATE DATABASE odoo OWNER db;\""

echo "[3/4] Importando datos de producción en la base de datos 'odoo'..."
gunzip -c "$DUMP_FILE" | ddev exec -s db "psql -U db -d odoo -q" > /dev/null

echo "[4/4] Restaurando Filestore en el volumen local 'odoo-data'..."
if [ -f "$FILESTORE_FILE" ]; then
    # Usar un contenedor auxiliar efímero para descomprimir el filestore en el volumen odoo-data
    docker run --rm \
        -v odoo-data:/target \
        -v "$PROJECT_DIR/scratch":/source \
        alpine sh -c "rm -rf /target/* && tar -xzf /source/odoo_filestore.tar.gz -C /target"
fi

echo "[*] Reiniciando servicio Odoo..."
ddev restart

echo "============================================="
echo " ✅ Entorno de producción clonado con éxito  "
echo " Acceso Local: https://odoo.ddev.site        "
echo " Odoo Directo: http://localhost:8069         "
echo "============================================="
