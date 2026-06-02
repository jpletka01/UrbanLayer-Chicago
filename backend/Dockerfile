# Stage 1: Build — install deps and pre-download models
FROM python:3.11-slim AS builder

WORKDIR /app

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

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy cached models
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

ENV HF_HOME=/root/.cache/huggingface
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface

COPY backend/ /app/backend/

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
