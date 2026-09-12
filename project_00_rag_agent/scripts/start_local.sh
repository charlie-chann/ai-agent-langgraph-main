#!/usr/bin/env bash
# 本地一键启动 project_00_rag_agent（API + 可选 Streamlit）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1. 安装依赖"
pip install -r requirements.txt -q

echo "==> 2. 配置本地环境 (APP_ENV=local)"
export APP_ENV="${APP_ENV:-local}"
if [[ ! -f .env.local && ! -f .env ]]; then
  if [[ -f .env.local.example ]]; then
    cp .env.local.example .env.local
    echo "    已创建 .env.local（来自 .env.local.example）"
  else
    cp .env.example .env
    echo "    已创建 .env（来自 .env.example）"
  fi
fi
echo "    APP_ENV=${APP_ENV}"

echo "==> 3. 检查 Ollama"
if ! curl -sf http://localhost:11434/api/tags >/dev/null; then
  echo "    [错误] Ollama 未运行，请先启动: ollama serve"
  echo "    并拉取模型: ollama pull qwen2.5:1.5b && ollama pull nomic-embed-text"
  exit 1
fi

echo "==> 4. 入库样例文档（若 chroma 为空）"
python - <<'PY'
from pathlib import Path
from app.knowledge.retriever import get_vectorstore
from app.knowledge.ingest import ingest_files

try:
    n = get_vectorstore()._collection.count()
except Exception:
    n = 0
if n == 0:
    sample = Path("sample_docs/company_knowledge_base.txt")
    if sample.exists():
        r = ingest_files([sample], force_rebuild=True)
        print("    ingest:", r)
    else:
        print("    [跳过] 无 sample_docs")
else:
    print(f"    已有 {n} chunks，跳过 ingest")
PY

echo "==> 5. 启动 API :8000"
echo "    另开终端运行 UI: streamlit run app_ui.py --server.port 8501"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
