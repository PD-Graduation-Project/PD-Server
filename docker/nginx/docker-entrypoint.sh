#!/bin/sh
# Entrypoint for nginx - generates self-signed cert only if not mounted

set -e

SSL_DIR="/etc/nginx/ssl"
CERT_FILE="${SSL_DIR}/server.crt"
KEY_FILE="${SSL_DIR}/server.key"

# Generate self-signed cert only if it doesn't exist
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "No SSL certificates found, generating self-signed certificate..."
    mkdir -p "$SSL_DIR"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
        2>/dev/null
    echo "Self-signed certificate generated (use real certs in production!)"
else
    echo "SSL certificates found, using mounted certificates"
fi

exec nginx -g "daemon off;"
