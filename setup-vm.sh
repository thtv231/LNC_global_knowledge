#!/usr/bin/env bash
# setup-vm.sh — Chạy một lần sau khi clone repo trên VM GCP
# Usage: bash setup-vm.sh
set -euo pipefail

echo "==> Kiểm tra Docker..."
docker --version
docker compose version

echo ""
echo "==> Tạo file .env từ template..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  Đã tạo .env — hãy điền các giá trị sau:"
  echo "    NEO4J_URI, NEO4J_PASSWORD"
  echo "    DEEPSEEK_API_KEY (hoặc DEEPSEEK_API_KEYS)"
  echo "    TAVILY_API_KEY"
  echo "    LLAMA_CLOUD_API_KEY  (nếu dùng CV analyzer)"
  echo ""
  echo "  Chạy: nano .env  rồi điền xong quay lại chạy:"
  echo "  bash setup-vm.sh start"
  exit 0
fi

if [ "${1:-}" = "start" ]; then
  echo "==> Build và khởi động services..."
  docker compose up -d --build

  echo ""
  echo "==> Đợi services sẵn sàng..."
  sleep 10
  docker compose ps

  echo ""
  echo "==> Health check..."
  curl -sf http://localhost:8000/health && echo " FastAPI OK" || echo " FastAPI chưa sẵn sàng"
  curl -sf http://localhost:3000/ && echo " Gateway OK" || echo " Gateway chưa sẵn sàng"

  echo ""
  echo "============================================================"
  echo "Backend đang chạy!"
  echo "  FastAPI  : http://$(curl -s ifconfig.me):8000"
  echo "  Gateway  : http://$(curl -s ifconfig.me):3000"
  echo ""
  echo "Cập nhật Vercel:"
  echo "  VITE_API_URL = http://$(curl -s ifconfig.me):3000"
  echo "============================================================"
fi
