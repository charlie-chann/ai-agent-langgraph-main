"""路径常量：所有 eval 脚本统一从这里取目录。"""
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EVAL_ROOT.parent
DATASETS_DIR = EVAL_ROOT / "datasets"
PROMPTS_DIR = EVAL_ROOT / "prompts"
RESULTS_DIR = EVAL_ROOT / "results"
BASELINE_PATH = EVAL_ROOT / "baseline.json"
RAG_PROJECT = REPO_ROOT / "project_01_rag_agent"
