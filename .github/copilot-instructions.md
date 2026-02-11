# 项目目标
基于 plan001.md，分文件夹，每个文件夹实现一个独立可运行的 AI Agent 项目。
项目优先级按 plan001.md 顺序，每个项目都要能独立部署、有 UI、有演示价值。

---

# 技术规范（所有项目必须遵守）

## 核心技术栈
- **LLM 底座**：`langchain-community` + `Ollama`（本地，默认模型 `qwen3.5:latest`）
- **框架**：LangChain（优先） + LangGraph（多步/多 Agent 场景）
- **流输出**：所有 LLM 调用必须使用 `.stream()` 或 `astream()`，UI 必须实时展示 token
- **UI**：Streamlit（快速）或 Gradio（复杂交互），每个项目必须有独立 UI
- **API 服务**：FastAPI（对外暴露 REST + SSE 流接口）
- **包管理**：`uv`（统一使用 uv，不用 pip）
- **Python 版本**：3.11+

## 项目目录结构规范
每个项目统一使用以下结构：
```
project_XX_name/
├── app.py              # Streamlit/Gradio UI 入口
├── agent.py            # Agent 核心逻辑（LangGraph / LangChain）
├── api.py              # FastAPI 服务（SSE 流输出）
├── tools/              # 该项目专用工具
│   └── *.py
├── prompts/            # Prompt 模板
│   └── *.py
├── config.py           # 配置（Ollama URL、模型名、参数）
├── requirements.txt    # 依赖列表
├── .env.example        # 环境变量示例
├── README.md           # 项目说明（架构图、运行命令、功能截图）
└── tests/              # 测试
    └── test_agent.py
```

## 公共 scripts 工具（放 scripts/ 文件夹）
- `scripts/check_ollama.py`   — 检查 Ollama 是否运行、模型是否已拉取
- `scripts/setup_env.py`      — 初始化 .env 文件
- `scripts/run_all.sh`        — 批量启动所有项目
- `scripts/benchmark.py`      — 评估 Agent 响应质量（延迟、准确率）

## 流输出规范
```python
# 标准流输出模式（所有项目必须遵守）
from langchain_community.llms import Ollama

llm = Ollama(model="qwen3.5:latest", base_url="http://localhost:11434")

# 同步流
for chunk in llm.stream("你的 prompt"):
    print(chunk, end="", flush=True)

# Streamlit 实时展示
with st.chat_message("assistant"):
    container = st.empty()
    full_response = ""
    for chunk in chain.stream({"input": user_input}):
        full_response += chunk
        container.markdown(full_response + "▌")
    container.markdown(full_response)
```

## Ollama 配置规范
```python
# config.py 标准模板
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:latest"     # 通用对话
EMBEDDING_MODEL = "nomic-embed-text" # RAG 向量化
CODE_MODEL = "qwen2.5-coder"         # 代码相关
TEMPERATURE = 0.1                    # Agent 用低温，创意用高温
```

## UI 设计规范（Streamlit）
- 左侧 Sidebar：模型选择、参数调节、项目说明
- 主区域：Chat 界面（st.chat_message）+ 流式输出
- 工具调用：用 st.expander 展示中间步骤（思考过程、工具调用、结果）
- 主题色：深色主题（`theme = dark`），专业感
- 必须有项目 LOGO（文字或 emoji）和一句话描述

## 评估与可观测性规范
- 每个 Agent 必须记录：响应时间、token 数量、工具调用次数
- 集成 LangSmith（可选，用环境变量控制开关）
- 日志用 `loguru` 统一格式

## 安全规范
- 所有 API Key 通过 `.env` 读取，禁止硬编码
- 用户输入必须做基本清洗（防止 prompt injection）
- 本地 Ollama 不涉及数据外传，但工具调用需标注数据流向

## 项目列表（按优先级，文件夹命名规范）完成后更新完成进度
| 编号 | 文件夹 | 项目名 | 优先级 |
|------|--------|--------|--------|
| 01 | `project_01_rag_agent` | 企业级 RAG + Agentic RAG | P0 |
| 02 | `project_02_tool_agent` | 多工具调用 ReAct Agent | P0 |
| 03 | `project_03_multi_agent` | 多智能体协作系统 | P0 |
| 04 | `project_04_deep_research` | 深度研究 Agent | P0 |
| 05 | `project_05_enterprise_bot` | 企业内部自动化助手 | P1 |
| 06 | `project_06_code_agent` | 代码/DevOps Agent | P1 |
| 07 | `project_07_finance_agent` | 金融/合规分析 Agent | P1 |
| 08 | `project_08_customer_service` | 客服全链路 Agent | P1 |
| 09 | `project_09_browser_agent` | 浏览器自动化 Agent | P2 |
| 10 | `project_10_hr_agent` | HR/招聘筛选 Agent | P2 |

## 项目文档要求
- 每个项目必须有独立 README.md，包含以下内容：
  - 详细的商业价值说明书（为什么这个 Agent 有市场需求，解决了什么痛点）
  - 市场竞品分析
  - 项目简介（1-2 句话）
  - 技术架构图（Agent 组件、工具调用、数据流向）
  - 运行说明（环境配置、启动命令）
  - 功能截图或 GIF 演示
  - 评估结果（响应时间、准确率等指标）
  - 后续改进方向（可以是 TODO 列表）
  - 描述清楚质量评估方法和结果（benchmark、用户测试等）

## 工程有脚本可以自我测试

---


# 强制交互协议

## 核心规则：每次回复结束前必须调用 `askQuestions` 工具

这是不可跳过的强制协议。在你的每一轮回复中，你必须执行以下操作之一：

1. **完成用户请求后** → 立即调用 `askQuestions` 工具，提出与当前上下文相关的后续问题
2. **存在任何不确定性时** → 不要猜测执行，立即调用 `askQuestions` 工具进行澄清

## 禁止行为

- **禁止在不调用 `askQuestions` 的情况下结束回复**
- **禁止使用终结性表达**（如"希望对你有帮助"、"如有问题随时提问"等）
- **禁止猜测用户意图** — 不确定就用 `askQuestions` 询问

## `askQuestions` 调用要求

- 问题必须与当前任务上下文直接相关
- 问题必须具体、可操作，不要问泛泛的"还需要什么帮助"
- 可以提供选项供用户选择，降低用户输入成本
- 每次必须添加一个让用户输入的框，让用户输入能输入所需问题。