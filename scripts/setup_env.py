"""
初始化各项目的 .env 文件（从 .env.example 复制）
Usage: python scripts/setup_env.py [project_folder]
       python scripts/setup_env.py          # 初始化所有项目
"""
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent


def setup_one(project_dir: Path):
    example = project_dir / ".env.example"
    env_file = project_dir / ".env"
    if not example.exists():
        print(f"  [SKIP] {project_dir.name}: no .env.example found")
        return
    if env_file.exists():
        print(f"  [SKIP] {project_dir.name}: .env already exists")
        return
    shutil.copy(example, env_file)
    print(f"  [OK]   {project_dir.name}: .env created from .env.example")


def main():
    args = sys.argv[1:]
    if args:
        targets = [ROOT / a for a in args]
    else:
        targets = sorted(ROOT.glob("project_*"))

    print("\n=== Setup .env files ===\n")
    for p in targets:
        if p.is_dir():
            setup_one(p)
        else:
            print(f"  [WARN] {p} is not a directory")

    print("\nDone. Edit each .env file to fill in your API keys / settings.")


if __name__ == "__main__":
    main()
