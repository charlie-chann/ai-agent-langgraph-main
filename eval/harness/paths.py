"""路径常量：所有 eval 脚本统一从这里取目录。"""
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EVAL_ROOT.parent
DATASETS_DIR = EVAL_ROOT / "datasets"
PROMPTS_DIR = EVAL_ROOT / "prompts"
RESULTS_DIR = EVAL_ROOT / "results"
BASELINE_PATH = EVAL_ROOT / "baseline.json"
RAG_PROJECT = REPO_ROOT / "project_01_rag_agent"
RAG_PROJECT_V00 = REPO_ROOT / "project_00_rag_agent"

RAG_PROJECTS = {
    "01": RAG_PROJECT,
    "00": RAG_PROJECT_V00,
}


def resolve_rag_project(project: str) -> Path:
    key = project.lstrip("project_").replace("_rag_agent", "")
    if key in RAG_PROJECTS:
        return RAG_PROJECTS[key]
    if project in RAG_PROJECTS:
        return RAG_PROJECTS[project]
    raise ValueError(f"Unknown project: {project}. Use 00 or 01.")
