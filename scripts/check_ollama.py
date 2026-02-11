"""
检查 Ollama 是否运行、模型是否已拉取
Usage: python scripts/check_ollama.py
"""
import sys
import httpx
from loguru import logger

OLLAMA_BASE_URL = "http://localhost:11434"

REQUIRED_MODELS = [
    "qwen2.5:1.5b",
    "nomic-embed-text",
]

OPTIONAL_MODELS = [
    "qwen2.5",
    "qwen2.5-coder",
]


def check_ollama_running() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        logger.success(f"Ollama is running at {OLLAMA_BASE_URL}")
        return True
    except Exception as e:
        logger.error(f"Ollama is NOT running: {e}")
        logger.info("Start Ollama with:  ollama serve")
        return False


def list_pulled_models() -> list[str]:
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def has_model(required: str, pulled: list[str]) -> bool:
    """检查所需模型是否已拉取（支持带/不带 tag 的匹配）。"""
    req_base, _, req_tag = required.partition(":")
    for name in pulled:
        if name == required:
            return True
        base, _, tag = name.partition(":")
        if base != req_base:
            continue
        if not req_tag or not tag or req_tag == tag:
            return True
    return False


def check_models(pulled: list[str]) -> bool:
    all_ok = True
    for model in REQUIRED_MODELS:
        if has_model(model, pulled):
            logger.success(f"  [REQUIRED] {model} ✓")
        else:
            logger.warning(f"  [REQUIRED] {model} ✗  →  run: ollama pull {model}")
            all_ok = False
    for model in OPTIONAL_MODELS:
        if has_model(model, pulled):
            logger.info(f"  [OPTIONAL] {model} ✓")
        else:
            logger.info(f"  [OPTIONAL] {model} not pulled  →  ollama pull {model}")
    return all_ok


def main():
    logger.remove()
    logger.add(sys.stderr, format="<level>{level: <8}</level> {message}")

    print("\n=== Ollama Environment Check ===\n")
    if not check_ollama_running():
        sys.exit(1)

    pulled = list_pulled_models()
    logger.info(f"Pulled models: {pulled}")

    ok = check_models(pulled)
    if ok:
        logger.success("\nAll required models are available. Ready to go!")
    else:
        logger.warning("\nSome required models are missing. Pull them before running projects.")
        sys.exit(1)


if __name__ == "__main__":
    main()
