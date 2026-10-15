#!/bin/bash
ssh developer@164.68.101.69 << 'EOF'
curl -sL http://127.0.0.1:8069/web/login | grep -o '/web/assets/[^"]*' | head -n 10
EOF