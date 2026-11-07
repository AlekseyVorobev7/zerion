#!/usr/bin/env bash
# One-time server setup (Debian/Ubuntu). Run as root on the target host:
#   bash setup-server.sh
set -euo pipefail

apt-get update -y
apt-get install -y nginx rsync python3 curl

mkdir -p /var/www/zerion /opt/noctra
cp "$(dirname "$0")/noctra-api.service" /etc/systemd/system/noctra-api.service
cp "$(dirname "$0")/tg-setup.sh" /opt/noctra/tg-setup.sh
systemctl daemon-reload
cp "$(dirname "$0")/nginx.conf" /etc/nginx/sites-available/zerion
ln -sf /etc/nginx/sites-available/zerion /etc/nginx/sites-enabled/zerion
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable --now nginx
systemctl reload nginx
echo "nginx ready, serving /var/www/zerion"
