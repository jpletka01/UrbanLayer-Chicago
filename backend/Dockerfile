# Stage 1: Build — install deps and pre-download models
FROM python:3.11-slim AS builder

WORKDIR /app

# System libs needed by WeasyPrint (build + runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (avoids pulling CUDA ~2GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.prod.txt .
RUN pip install --no-cache-dir -r requirements.prod.txt

# Pre-download HuggingFace models so they're baked into the layer
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-base-en-v1.5'); \
CrossEncoder('BAAI/bge-reranker-v2-m3')"

# Stage 2: Runtime — copy only what's needed
FROM python:3.11-slim

WORKDIR /app

# System libs needed by WeasyPrint at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -r app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy cached models (owned by app user)
COPY --from=builder --chown=app /root/.cache/huggingface /home/app/.cache/huggingface

ENV HF_HOME=/home/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/app/.cache/huggingface

COPY backend/ /app/backend/

# Runtime data files needed by geo.py, transit.py, and the zoning cache (zoning_cache.py).
COPY ingestion/data/community_areas.geojson /app/ingestion/data/community_areas.geojson
COPY ingestion/data/transit_stations.json /app/ingestion/data/transit_stations.json
COPY ingestion/data/zoning_cache.json /app/ingestion/data/zoning_cache.json
COPY ingestion/data/chrs_orange_red.json.gz /app/ingestion/data/chrs_orange_red.json.gz

# Create data + uploads dirs for the SQLite volume mount
RUN mkdir -p /app/backend/data/uploads && chown -R app:app /app/backend/data

USER app

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
