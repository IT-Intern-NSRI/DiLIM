#!/usr/bin/env bash
#
# Provisions a bare Oracle Cloud "Always Free" VM (tested against the
# default Ubuntu 22.04 image, both the ARM "Ampere A1" and x86
# "VM.Standard.E2.1.Micro" Always Free shapes) into a working WordPress
# host: Nginx + PHP-FPM + MySQL + WordPress core + WP-CLI, plus the
# local firewall rules those Oracle images ship locked-down by default.
#
# This script only does what can be automated *inside* the VM. Two
# things still need to happen outside it, and are NOT done here:
#   1. Opening ports 80/443 in the VCN's Security List / Network
#      Security Group, in the OCI web console (see README Part 1B,
#      step 2). Without this, nothing below will be reachable at all,
#      no matter what the local firewall allows.
#   2. Pointing a real domain (or free DDNS hostname) at this VM's
#      public IP, then running `sudo certbot --nginx -d your-domain`
#      once DNS has propagated (see README Part 1B, step 5). Certbot is
#      installed by this script but deliberately not run automatically,
#      since it will fail loudly if DNS isn't ready yet.
#
# Usage (run as a user with sudo, e.g. the default `ubuntu` user):
#   chmod +x oracle_cloud_setup.sh
#   ./oracle_cloud_setup.sh your-domain.example.com
#
# The domain argument is only used to build the Nginx server block's
# `server_name`; you can pass the VM's bare IP address instead if you
# don't have a domain yet and fix it up in
# /etc/nginx/sites-available/wordpress later.

set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 <domain-or-ip>"
  echo "Example: $0 labname.duckdns.org"
  exit 1
fi

WP_DIR="/var/www/wordpress"
DB_NAME="wordpress"
DB_USER="wordpress"
DB_PASS="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)"

echo "==> Updating packages"
sudo apt-get update -y
sudo apt-get upgrade -y

echo "==> Installing Nginx, MySQL, PHP-FPM and required PHP extensions"
sudo apt-get install -y \
  nginx mysql-server \
  php-fpm php-mysql php-curl php-gd php-mbstring php-xml php-zip php-intl \
  unzip curl

echo "==> Creating MySQL database and user for WordPress"
sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "==> Installing WP-CLI"
if ! command -v wp >/dev/null 2>&1; then
  curl -sO https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
  chmod +x wp-cli.phar
  sudo mv wp-cli.phar /usr/local/bin/wp
fi

echo "==> Downloading WordPress core into ${WP_DIR}"
sudo mkdir -p "$WP_DIR"
sudo chown -R "$USER":"$USER" "$WP_DIR"
if [ ! -f "$WP_DIR/wp-settings.php" ]; then
  wp core download --path="$WP_DIR"
fi

echo "==> Writing wp-config.php"
if [ ! -f "$WP_DIR/wp-config.php" ]; then
  wp config create \
    --path="$WP_DIR" \
    --dbname="$DB_NAME" \
    --dbuser="$DB_USER" \
    --dbpass="$DB_PASS" \
    --dbhost="localhost" \
    --skip-check
fi

sudo chown -R www-data:www-data "$WP_DIR"
sudo find "$WP_DIR" -type d -exec chmod 755 {} \;
sudo find "$WP_DIR" -type f -exec chmod 644 {} \;

echo "==> Configuring Nginx server block for ${DOMAIN}"
NGINX_CONF="/etc/nginx/sites-available/wordpress"
PHP_SOCK="$(sudo find /run/php -name '*.sock' | head -n1)"

sudo tee "$NGINX_CONF" >/dev/null <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    root ${WP_DIR};
    index index.php index.html;

    client_max_body_size 64M;

    location / {
        try_files \$uri \$uri/ /index.php?\$args;
    }

    location ~ \.php\$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:${PHP_SOCK};
    }

    location ~ /\.ht {
        deny all;
    }
}
NGINX

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/wordpress
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx mysql php*-fpm

echo "==> Opening HTTP/HTTPS in the VM's local firewall"
# Oracle's stock Ubuntu images ship with iptables rules that DROP most
# inbound traffic by default (SSH is allowed; almost nothing else is).
# This is separate from - and in addition to - the OCI Security List /
# NSG, which must also allow 80/443 (done in the OCI console, not here).
sudo apt-get install -y iptables-persistent >/dev/null 2>&1 || true
sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || \
  sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || \
  sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save >/dev/null 2>&1 || sudo iptables-save | sudo tee /etc/iptables/rules.v4 >/dev/null

echo "==> Installing Certbot (Let's Encrypt) - not run yet, see next steps below"
sudo apt-get install -y certbot python3-certbot-nginx

echo ""
echo "================================================================"
echo " Base stack installed. Remaining steps (see README Part 1B):"
echo "================================================================"
echo " MySQL root access is via 'sudo mysql' (socket auth) as usual."
echo " WordPress DB name: ${DB_NAME}"
echo " WordPress DB user: ${DB_USER}"
echo " WordPress DB pass: ${DB_PASS}"
echo " (save that password somewhere safe - it is not printed again)"
echo ""
echo " 1. In the OCI console, confirm the VCN Security List / NSG for"
echo "    this instance allows ingress on TCP 80 and 443 from 0.0.0.0/0."
echo " 2. Point ${DOMAIN} (A record) at this VM's public IP, and wait"
echo "    for DNS to propagate."
echo " 3. Once DNS resolves, run:"
echo "      sudo certbot --nginx -d ${DOMAIN}"
echo "    to issue a free TLS certificate and auto-configure HTTPS."
echo " 4. Visit https://${DOMAIN}/ and finish the WordPress install"
echo "    wizard (site title, admin account, etc.)."
echo " 5. Continue with README Part 1 steps 2-5: install Pods, copy"
echo "    wordpress_theme/ into the active theme, copy"
echo "    mu-plugins/force-login.php into wp-content/mu-plugins/, and"
echo "    generate an Application Password."
echo "================================================================"
