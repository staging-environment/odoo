#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo " Instalación de Docker y DDEV en Ubuntu 24.04"
echo "============================================="

# 1. Prerrequisitos de sistema
echo "[1/4] Instalando dependencias del sistema..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 2. Instalar Docker CE Oficial
echo "[2/4] Configurando repositorio oficial de Docker CE..."
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
fi

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Añadir usuario actual al grupo docker
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

# 3. Instalar DDEV Oficial
echo "[3/4] Configurando repositorio oficial de DDEV..."
if [ ! -f /etc/apt/keyrings/ddev.gpg ]; then
    curl -fsSL https://pkg.ddev.com/apt/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/ddev.gpg > /dev/null
    sudo chmod a+r /etc/apt/keyrings/ddev.gpg
fi

echo "deb [signed-by=/etc/apt/keyrings/ddev.gpg] https://pkg.ddev.com/apt/ * *" | sudo tee /etc/apt/sources.list.d/ddev.list > /dev/null

sudo apt-get update
sudo apt-get install -y ddev

# 4. Configurar certificados locales de DDEV
echo "[4/4] Inicializando DDEV mkcert..."
ddev config global --instrumentation-opt-in=false || true
mkcert -install || true

echo "============================================="
echo " ✅ Docker y DDEV instalados correctamente"
echo "============================================="
