FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers + pdf handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (core only — marker-pdf is too heavy for Cloud Run)
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

# Pre-download embedding model into image (~500MB)
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('intfloat/multilingual-e5-base', cache_folder='/app/.model_cache')"

# Copy source code
COPY api/ api/
COPY pipeline/ pipeline/
COPY retrieval/ retrieval/
COPY embeddings/ embeddings/
COPY graph/ graph/
COPY apps/cv_analyzer/ apps/cv_analyzer/

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
ENV TRANSFORMERS_CACHE=/app/.model_cache

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
