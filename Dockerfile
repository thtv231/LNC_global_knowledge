FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

COPY api/        api/
COPY pipeline/   pipeline/
COPY retrieval/  retrieval/
COPY embeddings/ embeddings/
COPY graph/      graph/
COPY apps/cv_analyzer/ apps/cv_analyzer/

ENV TRANSFORMERS_CACHE=/app/.model_cache
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
