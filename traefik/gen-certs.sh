#!/bin/bash
# Tạo self-signed SSL certificate cho devnotes.dev
mkdir -p certs

openssl req -x509 -nodes -days 3650 \
  -newkey rsa:2048 \
  -keyout certs/devnotes.key \
  -out certs/devnotes.crt \
  -subj "/CN=devnotes.dev" \
  -addext "subjectAltName=DNS:devnotes.local,DNS:*.devnotes.local"

echo "✅ Cert created: certs/devnotes.crt + certs/devnotes.key"
