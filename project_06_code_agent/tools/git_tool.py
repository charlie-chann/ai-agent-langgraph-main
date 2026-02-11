# tools/git_tool.py — sandboxed git operations
import subprocess
from pathlib import Path
from langchain_core.tools import tool
from loguru import logger

from config import SANDBOX_DIR

SANDBOX = Path(SANDBOX_DIR).resolve()

ALLOWED_GIT_CMDS = {"status", "log", "diff", "add", "commit", "init", "branch", "show"}


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"git error: {err or out}"
        return out or "(no output)"
    except FileNotFoundError:
        return "git not found in PATH"
    except subprocess.TimeoutExpired:
        return "git command timed out"
    except Exception as e:
        return f"Error: {e}"


@tool
def git_status() -> str:
    """Show git status of the code workspace."""
    return _run_git(["status", "--short"], SANDBOX)


@tool
def git_log(n: int = 5) -> str:
    """Show last N git commits. Input: number of commits (default 5)."""
    n = max(1, min(int(n), 20))
    return _run_git(["log", f"--oneline", f"-{n}"], SANDBOX)


@tool
def git_diff() -> str:
    """Show unstaged changes in the code workspace."""
    return _run_git(["diff"], SANDBOX)


@tool
def git_init_and_commit(message: str = "Initial commit") -> str:
    """Initialize git repo and make initial commit in workspace.
    Input: commit message string.
    Returns: outcome text.
    """
    SANDBOX.mkdir(exist_ok=True)
    # init if not already initialized
    git_dir = SANDBOX / ".git"
    if not git_dir.exists():
        _run_git(["init"], SANDBOX)
        _run_git(["config", "user.email", "agent@local"], SANDBOX)
        _run_git(["config", "user.name", "Code Agent"], SANDBOX)
    add_out = _run_git(["add", "."], SANDBOX)
    commit_out = _run_git(["commit", "-m", message[:200]], SANDBOX)
    logger.info(f"[git_commit] {message!r}")
    return f"{add_out}\n{commit_out}"
