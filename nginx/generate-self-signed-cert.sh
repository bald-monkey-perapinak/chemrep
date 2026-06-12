#!/bin/bash
# Generate self-signed SSL certificate for development
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$SCRIPT_DIR/certs"

mkdir -p "$CERT_DIR"

echo "Generating self-signed SSL certificate..."
echo "Output directory: $CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=ChemRep/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1"

chmod 600 "$CERT_DIR/key.pem"
chmod 644 "$CERT_DIR/cert.pem"

echo "Certificate generated:"
echo "  $CERT_DIR/cert.pem"
echo "  $CERT_DIR/key.pem"
echo ""
echo "Valid for 365 days. For production, replace with a real certificate (e.g. Let's Encrypt)."
