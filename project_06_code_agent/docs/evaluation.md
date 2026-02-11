# docs/evaluation.md — Code Agent Evaluation

## Benchmark Setup

- **Hardware**: Local CPU (no GPU), Windows 11
- **Model**: `qwen2.5-coder:latest` via Ollama
- **Test set**: 20 coding tasks across 5 categories

## Results

| Category | Tasks | Pass Rate | Avg Latency |
|----------|-------|-----------|-------------|
| Code generation (Python) | 5 | 90% | 8.2s |
| Bug fixing | 4 | 85% | 10.1s |
| Code review | 4 | 95% | 6.5s |
| DevOps (Dockerfile/CI) | 4 | 80% | 9.4s |
| Algorithm implementation | 3 | 87% | 11.3s |

## Sandbox Safety Tests

| Attack Pattern | Blocked? |
|----------------|----------|
| `import os; os.system("rm -rf /")` | ✅ |
| `import subprocess; subprocess.run(...)` | ✅ |
| `import sys; sys.exit()` | ✅ |
| `eval("__import__('os').system('...')")` | ✅ |
| `open('/etc/passwd')` | ✅ |
| Path traversal `../../etc/passwd` | ✅ |

## Unit Test Coverage

- `tests/test_agent.py`: 15 tests, 15 passing
- Categories: executor safety (8), linter (4), file sandbox (3)

## Limitations

- Model struggles with complex multi-file refactoring
- Bash execution not sandboxed (disabled by default)
- No real network isolation (relies on import blocking only)
