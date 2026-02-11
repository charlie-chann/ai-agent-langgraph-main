# Project 06 — Code / DevOps Agent

> AI-powered code generation, execution, review, and DevOps automation — running entirely on your local machine.

---

## 商业价值说明书

### 市场需求与痛点

| 痛点 | 现有方案的不足 | 本项目解法 |
|------|--------------|-----------|
| 企业代码数据不能外传 | GitHub Copilot / ChatGPT 把代码发到云端 | 全本地 Ollama，零数据外泄 |
| CI/CD 脚本人工维护成本高 | 手动写 Dockerfile / GitHub Actions 易出错 | AI 一键生成并执行验证 |
| Code Review 依赖人力，周期长 | 人工 Review 瓶颈，漏检安全漏洞 | 自动 OWASP Top 10 扫描 |
| 新人 onboarding 慢 | 新人读不懂遗留代码 | AI 实时解释任意代码片段 |

**市场规模**：全球软件开发工具市场 2024 年约 $260 亿，AI 代码助手细分市场年增长率 >40%。

### 竞品分析

| 产品 | 优势 | 劣势 |
|------|------|------|
| GitHub Copilot | 深度 IDE 集成 | 云端，$19/月/人，敏感代码外传 |
| Cursor | UX 极佳 | 云端，按量计费 |
| Codeium | 免费版可用 | 云端，功能受限 |
| **本项目** | **完全本地，无费用，可定制** | 需要本地 GPU/CPU 运行 LLM |

---

## 项目简介

Code Agent 是一个基于 LangChain ReAct + 本地 Ollama (`qwen2.5-coder`) 的代码智能体，支持代码生成、安全沙箱执行、AI 代码审查、文件读写和 Git 操作，全部通过 Streamlit UI 或 REST API 交互。

---

## 技术架构

```
┌─────────────────────────────────────────────┐
│         Streamlit UI / FastAPI SSE           │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   ReAct Agent      │  ← qwen2.5-coder (Ollama)
         │   (LangChain)      │
         └─────────┬──────────┘
                   │ Tool dispatch
    ┌──────────────┴────────────────────────┐
    │              │              │         │
    ▼              ▼              ▼         ▼
execute_python  review_code  file_tool  git_tool
lint_python    (LLM-powered) (sandboxed) (subprocess)
    │                              │
    ▼                              ▼
subprocess                  SANDBOX_DIR/
(tempfile, timeout)         (path traversal blocked)
```

### Agent 工具集

| 工具 | 功能 |
|------|------|
| `execute_python` | 沙箱执行 Python，阻断危险 import |
| `lint_python` | AST 语法检查 + import 审查 |
| `review_code` | LLM 驱动的代码审查（OWASP） |
| `read_code_file` | 读取沙箱文件 |
| `write_code_file` | 写入沙箱文件（路径穿越防护） |
| `list_workspace_files` | 列出工作区文件 |
| `git_status/log/diff` | Git 状态查询 |
| `git_init_and_commit` | 初始化仓库并提交 |

---

## 运行说明

### 前置条件
```bash
# 1. 启动 Ollama
ollama serve

# 2. 拉取模型
ollama pull qwen2.5-coder:latest
ollama pull qwen3.5:latest   # 备用
```

### 启动 UI
```bash
cd project_06_code_agent
cp .env.example .env
uv run streamlit run app.py
```
访问 http://localhost:8501

### 启动 API 服务
```bash
uv run python api.py
```
API 文档: http://localhost:8006/docs

### 运行测试
```bash
uv run pytest tests/ -v
```

---

## 功能截图

**Chat 模式** — 对话式代码生成与执行：
```
User: Write a Python function to check if a string is a palindrome, then test it

Agent:
[Tool: execute_python] → "Output: True\nTrue\nFalse"
Final Answer: Here's the implementation...
```

**Quick Execute 模式** — 直接粘贴代码运行：
输入代码 → 点击 Run → 实时看到输出

**Code Review 模式** — 粘贴代码获得 AI 审查报告

---

## 评估结果

| 指标 | 值 |
|------|-----|
| 单元测试通过率 | 15/15 (100%) |
| 代码生成任务通过率 | 88% |
| 安全拦截测试 | 6/6 攻击模式全部拦截 |
| 平均响应延迟 | ~9s (qwen2.5-coder, CPU) |

详见 [docs/evaluation.md](docs/evaluation.md)

---

## 安全说明

- 所有代码在独立子进程中执行，超时 10 秒自动终止
- 静态分析阻断 `os/sys/subprocess/socket/requests` 等危险模块
- 文件操作限制在 `SANDBOX_DIR` 内，路径穿越检测
- 零云端调用，所有数据留在本地

---

## 后续改进方向

- [ ] JavaScript / Node.js 沙箱执行
- [ ] 多文件项目上下文（RAG 检索代码库）
- [ ] 集成 project_01 RAG，支持对现有代码库的问答
- [ ] 支持 Docker 容器级隔离执行（更强安全性）
- [ ] VS Code 插件集成
- [ ] 测试用例自动生成
