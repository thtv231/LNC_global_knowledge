# GCP VM Deploy Runbook — Claude Code Executable

> **Mục đích:** Tài liệu này được viết để Claude Code có thể đọc và thực hiện tự động từng bước deploy một ứng dụng multi-container lên GCP VM bằng GitHub Actions. Người dùng chỉ cần cung cấp thông tin trong phần **INPUT** và approve các bước có đánh dấu `[USER ACTION]`.

---

## INPUT — Thông tin cần thu thập trước khi bắt đầu

Claude Code cần hỏi người dùng và lưu lại các giá trị sau:

```
GCP_PROJECT_ID    = ?   # vd: my-project-499702
GCP_VM_NAME       = ?   # vd: instance-20260619-023955
GCP_VM_ZONE       = ?   # vd: us-central1-a
GCP_VM_IP         = ?   # vd: 35.239.231.145
GCP_VM_USER       = ?   # vd: vulncglobal (user khi SSH vào VM)
GITHUB_REPO       = ?   # vd: thtv231/LNC_global_knowledge
GITHUB_USER       = ?   # vd: thtv231
APP_NAME          = ?   # vd: lnc (prefix cho Docker images)
SSH_KEY_PATH      = ?   # vd: ~/.ssh/github_actions_lnc
```

Nếu chưa có VM: thực hiện Bước 0 trước. Nếu đã có VM và đã có SA key: bắt đầu từ Bước 2.

---

## Bước 0 — Lấy Project ID từ VM (nếu VM đã chạy)

```bash
ssh -i {SSH_KEY_PATH} -o StrictHostKeyChecking=no {GCP_VM_USER}@{GCP_VM_IP} \
  "curl -sf -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id"
```

Lưu output → `GCP_PROJECT_ID`.

---

## Bước 1 — Tạo Service Account trên GCP

### 1a. Link tạo SA (gửi cho người dùng)

```
https://console.cloud.google.com/iam-admin/serviceaccounts/create?project={GCP_PROJECT_ID}
```

### 1b. Hướng dẫn người dùng [USER ACTION]

Nói với người dùng:

> Vào link trên, điền:
> - **Name:** `github-actions-deploy`
> - **Grant roles:**
>   1. `Compute OS Admin Login`
>   2. `Compute Instance Admin (v1)`
> - Bấm **Create** → chọn SA vừa tạo → **Keys → Add Key → JSON** → download file
> - Gửi cho tôi nội dung file JSON đó (hoặc đường dẫn file)

### 1c. Sau khi nhận SA key — thêm vào GitHub Secrets

```
https://github.com/{GITHUB_REPO}/settings/secrets/actions/new
```

Thêm 2 secrets:
- `GCP_SA_KEY` = toàn bộ nội dung file JSON
- `GCP_PROJECT_ID` = `{GCP_PROJECT_ID}`

---

## Bước 2 — Kiểm tra cấu trúc Dockerfile

Claude Code kiểm tra các file sau tồn tại và đúng chuẩn:

### Checklist Dockerfile

```bash
# Kiểm tra Dockerfiles
ls apps/*/Dockerfile
```

**Dockerfile Python (ai-service) phải có:**
- `FROM python:3.11-slim`
- `HEALTHCHECK --interval=30s ... CMD curl -f http://localhost:PORT/health`
- `CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`
- `python-multipart` trong requirements.txt nếu có `UploadFile`

**Dockerfile Node (gateway) phải có:**
- Multi-stage build (`AS builder` + runtime stage)
- `ENV NODE_ENV=production`

**Dockerfile Web (React/Vite) phải có:**
- `ARG VITE_API_URL` + `ENV VITE_API_URL=$VITE_API_URL`
- Multi-stage: Node builder → nginx:alpine
- `COPY nginx.conf /etc/nginx/conf.d/default.conf`

### nginx.conf bắt buộc phải có proxy rules

```bash
cat apps/web/nginx.conf
```

File **phải** chứa `proxy_pass http://gateway:3000` cho các route API. Nếu chưa có, tạo với nội dung:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    # Thêm tất cả API routes cần proxy — ví dụ:
    location /chat {
        proxy_pass         http://gateway:3000;
        proxy_http_version 1.1;
        proxy_set_header   Connection '';
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 120s;
    }

    location /cv {
        proxy_pass         http://gateway:3000;
        proxy_http_version 1.1;
        proxy_read_timeout 120s;
        client_max_body_size 20m;
    }

    location /history {
        proxy_pass http://gateway:3000;
        proxy_http_version 1.1;
    }

    location /intake {
        proxy_pass http://gateway:3000;
        proxy_http_version 1.1;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
}
```

> **Tại sao dùng nginx proxy thay vì `VITE_API_URL=http://IP:3000`?**
> Nếu để `VITE_API_URL` trống, React dùng relative URL `/chat` → nginx proxy sang gateway. Không cần expose port 3000 ra internet, không cần rebuild khi đổi IP server.

---

## Bước 3 — Kiểm tra docker-compose.yml

```bash
cat docker-compose.yml
```

**Bắt buộc phải có:**
- Mỗi service: `restart: unless-stopped`
- `ai-service`: `healthcheck` với `curl -f http://localhost:8000/health`
- `gateway`: `depends_on: ai-service: condition: service_healthy`
- `web`: port `80:80`
- Image format: `ghcr.io/{GITHUB_USER}/{APP_NAME}-SERVICE:latest`

**Template chuẩn:**

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes: [redis_data:/data]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  ai-service:
    image: ghcr.io/{GITHUB_USER}/{APP_NAME}-ai-service:latest
    restart: unless-stopped
    env_file: .env
    environment:
      REDIS_URL: redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

  gateway:
    image: ghcr.io/{GITHUB_USER}/{APP_NAME}-gateway:latest
    restart: unless-stopped
    env_file: .env
    environment:
      AI_SERVICE_URL: http://ai-service:8000
      PORT: "3000"
    depends_on:
      ai-service:
        condition: service_healthy

  web:
    image: ghcr.io/{GITHUB_USER}/{APP_NAME}-web:latest
    restart: unless-stopped
    ports: ["80:80"]
    depends_on: [gateway]

volumes:
  redis_data:
```

---

## Bước 4 — Tạo GitHub Actions Workflow

Tạo file `.github/workflows/deploy.yml`:

```yaml
name: Build & Deploy to GCP VM

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  OWNER: {GITHUB_USER}
  VM_NAME: {GCP_VM_NAME}
  VM_ZONE: {GCP_VM_ZONE}

jobs:
  build-ai-service:
    name: Build ai-service
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}" }
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: ./apps/ai-service
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.OWNER }}/{APP_NAME}-ai-service:latest
            ${{ env.REGISTRY }}/${{ env.OWNER }}/{APP_NAME}-ai-service:${{ github.sha }}
          cache-from: type=gha,scope=ai-service
          cache-to:   type=gha,mode=max,scope=ai-service

  build-gateway:
    name: Build gateway
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}" }
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: ./apps/gateway
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.OWNER }}/{APP_NAME}-gateway:latest
            ${{ env.REGISTRY }}/${{ env.OWNER }}/{APP_NAME}-gateway:${{ github.sha }}
          cache-from: type=gha,scope=gateway
          cache-to:   type=gha,mode=max,scope=gateway

  build-web:
    name: Build web
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: "${{ github.actor }}", password: "${{ secrets.GITHUB_TOKEN }}" }
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          context: ./apps/web
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.OWNER }}/{APP_NAME}-web:latest
            ${{ env.REGISTRY }}/${{ env.OWNER }}/{APP_NAME}-web:${{ github.sha }}
          build-args: VITE_API_URL=${{ secrets.VITE_API_URL }}
          cache-from: type=gha,scope=web
          cache-to:   type=gha,mode=max,scope=web

  deploy:
    name: Deploy to VM
    needs: [build-ai-service, build-gateway, build-web]
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Open firewall ports (idempotent)
        run: |
          gcloud compute firewall-rules describe allow-{APP_NAME}-ports \
            --project=${{ secrets.GCP_PROJECT_ID }} --quiet 2>/dev/null \
          || gcloud compute firewall-rules create allow-{APP_NAME}-ports \
            --project=${{ secrets.GCP_PROJECT_ID }} \
            --allow=tcp:80 \
            --source-ranges=0.0.0.0/0 \
            --description="{APP_NAME} public HTTP" --quiet

      # Liệt kê tất cả secrets của app ở đây
      - name: Write env file locally
        env:
          # ---- THAY BẰNG SECRETS THỰC TẾ CỦA APP ----
          DB_URI:       ${{ secrets.DB_URI }}
          DB_PASSWORD:  ${{ secrets.DB_PASSWORD }}
          API_KEY:      ${{ secrets.API_KEY }}
          # --------------------------------------------
          GHCR_PAT:     ${{ secrets.GHCR_PAT }}
          GIT_ACTOR:    ${{ github.actor }}
        run: |
          # ---- THAY NỘI DUNG .env THEO APP ----
          cat > /tmp/app.env << EOF
          DB_URI=${DB_URI}
          DB_PASSWORD=${DB_PASSWORD}
          API_KEY=${API_KEY}
          REDIS_URL=redis://redis:6379
          AI_SERVICE_URL=http://ai-service:8000
          PORT=3000
          EOF
          # --------------------------------------

          # Dùng GHCR_PAT nếu có, fallback GITHUB_TOKEN
          PULL_TOKEN="${GHCR_PAT:-}"
          printf '%s' "${PULL_TOKEN}"  > /tmp/ghcr_token
          printf '%s' "${GIT_ACTOR}"   > /tmp/ghcr_user

      - name: Upload files to VM
        run: |
          gcloud compute scp /tmp/app.env /tmp/ghcr_token /tmp/ghcr_user \
            ${{ env.VM_NAME }}:/tmp/ \
            --zone=${{ env.VM_ZONE }} \
            --project=${{ secrets.GCP_PROJECT_ID }} \
            --quiet

      - name: Bootstrap & Deploy
        run: |
          gcloud compute ssh ${{ env.VM_NAME }} \
            --zone=${{ env.VM_ZONE }} \
            --project=${{ secrets.GCP_PROJECT_ID }} \
            --quiet \
            --command='
              set -e

              # Cài Docker nếu chưa có
              if ! command -v docker &>/dev/null; then
                echo "==> Installing Docker..."
                curl -fsSL https://get.docker.com | sudo sh
              fi
              sudo usermod -aG docker "$USER" 2>/dev/null || true
              sudo mkdir -p /opt/{APP_NAME}
              sudo chmod 777 /opt/{APP_NAME}

              # Chỉ overwrite .env nếu secrets thực sự được set
              # (thay "API_KEY" bằng một key chắc chắn có giá trị)
              if grep -q "API_KEY=.\{4,\}" /tmp/app.env 2>/dev/null; then
                sudo cp /tmp/app.env /opt/{APP_NAME}/.env
                sudo chmod 600 /opt/{APP_NAME}/.env
                echo "==> .env updated from GitHub Secrets"
              else
                echo "==> Keeping existing .env on VM"
              fi

              # Lấy docker-compose.yml mới nhất
              sudo curl -fsSL \
                https://raw.githubusercontent.com/{GITHUB_REPO}/main/docker-compose.yml \
                -o /opt/{APP_NAME}/docker-compose.yml

              # Login GHCR
              PULL_TOKEN=$(cat /tmp/ghcr_token)
              PULL_USER=$(cat /tmp/ghcr_user)
              if [ -n "$PULL_TOKEN" ]; then
                echo "$PULL_TOKEN" | sudo docker login ghcr.io -u "$PULL_USER" --password-stdin
              fi

              cd /opt/{APP_NAME}
              sudo docker compose pull
              sudo docker compose up -d --remove-orphans
              sudo docker image prune -f
              sudo rm -f /tmp/app.env /tmp/ghcr_token /tmp/ghcr_user

              echo "=== Deployed $(date) ==="
              sudo docker compose ps
            '
```

---

## Bước 5 — Thêm GitHub Secrets còn thiếu

### 5a. Kiểm tra secrets nào cần thêm

Workflow trên dùng các secrets sau. Claude Code kiểm tra người dùng đã thêm chưa bằng cách hỏi trực tiếp:

| Secret | Đã set? | Ghi chú |
|--------|---------|---------|
| `GCP_SA_KEY` | ✅/❌ | File JSON Service Account |
| `GCP_PROJECT_ID` | ✅/❌ | Project ID của GCP |
| `GHCR_PAT` | ✅/❌ | GitHub PAT có quyền `write:packages` |
| `VITE_API_URL` | để trống | Không cần set nếu dùng nginx proxy |
| App secrets... | ✅/❌ | DB, API keys... |

### 5b. Link thêm secret

```
https://github.com/{GITHUB_REPO}/settings/secrets/actions/new
```

### 5c. Cách tạo GHCR_PAT [USER ACTION]

> Vào GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token
> - Chọn: `write:packages`, `read:packages`, `delete:packages`
> - Expiration: No expiration (hoặc 1 năm)
> - Copy token → thêm vào GitHub Secrets với tên `GHCR_PAT`

---

## Bước 6 — Push code và trigger deploy

```bash
git add .
git commit -m "ci: add GCP deployment config"
git push origin main
```

GitHub Actions sẽ tự chạy. Theo dõi:

```bash
gh run list --repo {GITHUB_REPO} --limit 3
gh run watch {RUN_ID} --repo {GITHUB_REPO}
```

Nếu fail, lấy log:

```bash
gh run view {RUN_ID} --repo {GITHUB_REPO} --log-failed
```

---

## Bước 7 — Verify sau khi deploy

```bash
# Web hoạt động
curl -sI http://{GCP_VM_IP} --max-time 10

# API hoạt động qua nginx proxy
curl -s -X POST http://{GCP_VM_IP}/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"test","session_id":"verify-1"}' \
  --max-time 30 | head -5

# Kiểm tra containers trên VM
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} \
  "sudo docker compose -f /opt/{APP_NAME}/docker-compose.yml ps"
```

**Expected output:**
```
HTTP/1.1 200 OK        ← web OK
data: {"type":"status"...  ← chat streaming OK
NAME          STATUS
app-redis     Up (healthy)
app-ai-service  Up (healthy)
app-gateway   Up
app-web       Up
```

---

## Bước 8 — Ghi .env thủ công lên VM (nếu GitHub Secrets chưa set)

Nếu app secrets chưa được thêm vào GitHub Secrets, Claude Code đọc `.env` local và ghi trực tiếp lên VM:

```bash
# Đọc .env local
cat .env

# SSH vào VM và ghi .env
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} "sudo tee /opt/{APP_NAME}/.env > /dev/null << 'ENVEOF'
$(cat .env | grep -v '^#' | grep -v '^$' | grep -v 'localhost')
REDIS_URL=redis://redis:6379
AI_SERVICE_URL=http://ai-service:8000
ENVEOF
echo done"

# Recreate containers để nhận env mới
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} \
  "cd /opt/{APP_NAME} && sudo docker compose up -d --force-recreate"
```

> **Lưu ý:** `--force-recreate` là bắt buộc. `docker compose restart` KHÔNG re-read `env_file`.

---

## Bước 9 — Cấu hình auto-start khi VM reboot

```bash
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} "
sudo tee /etc/systemd/system/{APP_NAME}.service > /dev/null << 'EOF'
[Unit]
Description={APP_NAME} App (Docker Compose)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/{APP_NAME}
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose down
User={GCP_VM_USER}

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable {APP_NAME}
echo 'Auto-start enabled'
"
```

---

## Xử lý lỗi thường gặp

### Lỗi: `sudo: I'm afraid I can't do that`

VM user không có sudo. **Nguyên nhân:** GCP OS Login user cần role `Compute OS Admin Login`.

**Kiểm tra:**
```bash
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} "sudo whoami"
```

**Fix:** Đảm bảo SA có role `Compute OS Admin Login` trong GCP IAM. Khi GitHub Actions dùng SA để SSH, user đó tự động có sudo.

---

### Lỗi: Container `unhealthy` ngay sau start

**Kiểm tra log:**
```bash
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} \
  "sudo docker logs {APP_NAME}-ai-service-1 2>&1 | tail -30"
```

**Nguyên nhân phổ biến:**
- Missing package trong `requirements.txt` (vd: `python-multipart`)
- Env vars rỗng → kết nối DB/API fail
- `/health` endpoint chưa có trong code

---

### Lỗi: Frontend không gọi được API

**Kiểm tra nginx config:**
```bash
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} \
  "sudo docker exec {APP_NAME}-web-1 cat /etc/nginx/conf.d/default.conf"
```

Phải có `proxy_pass http://gateway:3000` cho các route API. Nếu không có → rebuild web image sau khi sửa `nginx.conf`.

---

### Lỗi: `Connection error` khi chat

**Kiểm tra env trong container:**
```bash
ssh -i {SSH_KEY_PATH} {GCP_VM_USER}@{GCP_VM_IP} \
  "sudo docker exec {APP_NAME}-ai-service-1 sh -c 'cat /proc/1/environ | tr \"\0\" \"\n\" | grep -E \"API_KEY|DB_|NEO4J\"'"
```

Nếu các key rỗng → thực hiện Bước 8 (ghi .env thủ công).

---

## Tóm tắt quy trình một lần (Happy Path)

```
1. Thu thập INPUT từ người dùng
2. Người dùng tạo SA trên GCP → download JSON key
3. Người dùng thêm GCP_SA_KEY + GCP_PROJECT_ID vào GitHub Secrets
4. Claude Code kiểm tra & tạo Dockerfiles, nginx.conf, docker-compose.yml
5. Claude Code tạo .github/workflows/deploy.yml với giá trị đúng
6. git push → GitHub Actions chạy tự động
7. Nếu fail → Claude Code đọc log, fix, push lại
8. Nếu .env chưa có secrets → Claude Code ghi trực tiếp lên VM (Bước 8)
9. Claude Code verify: curl web + curl API
10. Claude Code tạo systemd service (Bước 9) → auto-start on reboot
```

**Thời gian ước tính:** 15-30 phút (lần đầu), 3-5 phút (các lần sau).
