# Production RAG Agent — multi-stage Docker image
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/chroma_db /app/kg_store /tmp/rag_uploads_v2

ENV PYTHONUNBUFFERED=1 \
    OLLAMA_BASE_URL=http://ollama:11434 \
    REDIS_URL=redis://redis:6379/0 \
    DATABASE_URL=postgresql://rag:rag@postgres:5432/rag_checkpoint \
    CHECKPOINTER_BACKEND=postgres \
    LLM_PROVIDER=ollama \
    DEFAULT_MODEL=qwen2.5:1.5b \
    EMBEDDING_MODEL=nomic-embed-text

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default: API server (override in compose for UI)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
