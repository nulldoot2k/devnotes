Run command
```
# 1. Tạo cert
chmod +x gen-certs.sh && ./gen-certs.sh

# 2. Thêm domain vào hosts
echo "127.0.0.1 devnotes.dev" | sudo tee -a /etc/hosts

# 3. Khởi động Traefik
cd .. && docker compose up -d
```
