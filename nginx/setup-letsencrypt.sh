#!/bin/bash
# Setup Let's Encrypt SSL certificates for production
# Run once on the server before starting docker-compose
set -e

DOMAIN=${1:-localhost}
EMAIL=${2:-admin@chemrep.ru}
CERT_DIR="$(dirname "$0")/certs"

mkdir -p "$CERT_DIR"

if [ "$DOMAIN" = "localhost" ]; then
    echo "Domain is localhost — using self-signed certificate"
    ./generate-self-signed-cert.sh
    exit 0
fi

echo "Setting up Let's Encrypt for $DOMAIN..."

# Install certbot if not present
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update && apt-get install -y certbot
fi

# Get certificate
certbot certonly --standalone \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --cert-path "$CERT_DIR/cert.pem" \
    --key-path "$CERT_DIR/key.pem"

# Setup auto-renewal
echo "0 0,12 * * * certbot renew --quiet --post-hook 'docker restart nginx'" | crontab -

echo "Certificate installed:"
echo "  $CERT_DIR/cert.pem"
echo "  $CERT_DIR/key.pem"
echo ""
echo "Auto-renewal configured via cron."
echo "Start docker-compose with: docker-compose up -d"
