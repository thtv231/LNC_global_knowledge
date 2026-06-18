#!/usr/bin/env bash
# deploy-gcp.sh — Deploy FastAPI + NestJS Gateway to Google Cloud Run
# Usage: bash deploy-gcp.sh <GCP_PROJECT_ID>
set -euo pipefail

PROJECT_ID="${1:?Usage: bash deploy-gcp.sh <GCP_PROJECT_ID>}"
REGION="asia-southeast1"          # Singapore — gần Việt Nam nhất
API_SERVICE="lnc-api"
GW_SERVICE="lnc-gateway"
REGISTRY="gcr.io/${PROJECT_ID}"

echo "==> Project: $PROJECT_ID  |  Region: $REGION"

# ── 1. Auth & project ────────────────────────────────────────────────────────
gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --quiet

# ── 2. Build & push FastAPI ──────────────────────────────────────────────────
echo "==> Building FastAPI image..."
gcloud builds submit . \
  --tag "${REGISTRY}/${API_SERVICE}:latest" \
  --timeout=20m \
  --quiet

# ── 3. Deploy FastAPI to Cloud Run ──────────────────────────────────────────
echo "==> Deploying FastAPI to Cloud Run..."
gcloud run deploy "$API_SERVICE" \
  --image "${REGISTRY}/${API_SERVICE}:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 5 \
  --set-env-vars "\
NEO4J_URI=${NEO4J_URI},\
NEO4J_USER=${NEO4J_USER},\
NEO4J_PASSWORD=${NEO4J_PASSWORD},\
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY},\
DEEPSEEK_API_KEYS=${DEEPSEEK_API_KEYS},\
DEEPSEEK_MODEL=${DEEPSEEK_MODEL},\
DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL:-https://api.deepseek.com},\
TRANSFORMERS_CACHE=/app/.model_cache" \
  --quiet

API_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --format "value(status.url)")
echo "==> FastAPI deployed: $API_URL"

# ── 4. Build & push NestJS Gateway ──────────────────────────────────────────
echo "==> Building NestJS Gateway image..."
gcloud builds submit ./apps/gateway \
  --tag "${REGISTRY}/${GW_SERVICE}:latest" \
  --timeout=10m \
  --quiet

# ── 5. Deploy Gateway to Cloud Run ──────────────────────────────────────────
echo "==> Deploying Gateway to Cloud Run..."
gcloud run deploy "$GW_SERVICE" \
  --image "${REGISTRY}/${GW_SERVICE}:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 100 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "AI_SERVICE_URL=${API_URL},AI_SERVICE_TIMEOUT=120000" \
  --quiet

GW_URL=$(gcloud run services describe "$GW_SERVICE" \
  --region "$REGION" --format "value(status.url)")
echo "==> Gateway deployed: $GW_URL"

# ── 6. Update Vercel VITE_API_URL ───────────────────────────────────────────
echo ""
echo "============================================================"
echo "Deploy hoàn tất!"
echo ""
echo "  FastAPI  : $API_URL"
echo "  Gateway  : $GW_URL"
echo ""
echo "Cập nhật Vercel frontend:"
echo "  vercel env rm VITE_API_URL production --yes"
echo "  echo \"$GW_URL\" | vercel env add VITE_API_URL production"
echo "  vercel --prod --yes"
echo "============================================================"
