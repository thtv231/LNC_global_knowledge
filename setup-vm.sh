#!/usr/bin/env bash
# setup-vm.sh — Bootstrap GCP VM lần đầu
# Chạy với: bash setup-vm.sh
set -euo pipefail

echo "==> Cài Docker & Docker Compose..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "  Docker đã cài. Cần logout/login lại để dùng docker không cần sudo."
    echo "  Sau khi re-login, chạy lại: bash setup-vm.sh"
    exit 0
fi

docker --version
docker compose version

echo ""
echo "==> Tạo thư mục app..."
sudo mkdir -p /opt/lnc-app
sudo chown "$USER":"$USER" /opt/lnc-app

echo ""
echo "==> Mở firewall ports (nếu dùng ufw)..."
if command -v ufw &>/dev/null; then
    sudo ufw allow 80/tcp   || true
    sudo ufw allow 3000/tcp || true
    echo "  Port 80 (web) và 3000 (gateway) đã mở."
fi

echo ""
echo "============================================================"
echo "VM đã sẵn sàng!"
echo ""
echo "Bước tiếp theo — thêm GitHub Secrets vào repo:"
echo "  Settings → Secrets → Actions → New repository secret"
echo ""
echo "  GCP_VM_HOST        = $(curl -sf https://ifconfig.me 2>/dev/null || echo '<external IP>')"
echo "  GCP_VM_USER        = $USER"
echo "  GCP_VM_SSH_KEY     = <nội dung ~/.ssh/id_ed25519 (private key)>"
echo "  GHCR_PAT           = <GitHub PAT với quyền read:packages>"
echo "  VITE_API_URL       = http://$(curl -sf https://ifconfig.me 2>/dev/null || echo '<external IP>'):3000"
echo "  NEO4J_URI          = neo4j+s://xxx.databases.neo4j.io"
echo "  NEO4J_PASSWORD     = ..."
echo "  DEEPSEEK_API_KEY   = ..."
echo "  DEEPSEEK_API_KEYS  = key1,key2,..."
echo "  TAVILY_API_KEY     = ..."
echo "  GROQ_API_KEY       = ..."
echo "  GOOGLE_SHEET_WEBHOOK = ..."
echo ""
echo "Push code lên main → GitHub Actions tự động deploy!"
echo "============================================================"
