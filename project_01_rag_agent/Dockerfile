# RAG Agent API — Docker 镜像
# 构建: docker build -t rag-agent:1.0 .
# 运行: docker run -p 8001:8001 rag-agent:1.0

FROM python:3.11-slim

WORKDIR /app

# 系统依赖（部分文档解析库需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制业务代码
COPY api.py agent.py config.py ./
COPY prompts/ ./prompts/
COPY tools/ ./tools/

# 向量库与上传目录（运行时建议挂载卷覆盖）
RUN mkdir -p /app/chroma_db /tmp/rag_uploads

ENV PYTHONUNBUFFERED=1 \
    OLLAMA_BASE_URL=http://ollama:11434 \
    DEFAULT_MODEL=qwen2.5:1.5b \
    EMBEDDING_MODEL=nomic-embed-text

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
