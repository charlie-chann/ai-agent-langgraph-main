"""
prompts/agent_prompts.py — ReAct Agent 系统提示词

【职责】
1. 定义 ReAct Agent 的系统级 Prompt（角色、任务、工具使用规范）
2. 组装 ChatPromptTemplate，注入工具列表与对话历史占位符

【设计原因】
1. Prompt 与 agent.py 解耦：调文案不用改核心逻辑
2. {tools} / {tool_names} 由 LangChain 运行时填充，LLM 能知道有哪些工具
3. agent_scratchpad 占位符：ReAct 循环中「思考→调工具→观察」的中间步骤注入此处

【注意】
当前 agent.py 使用 create_react_agent() 默认 Prompt，本文件为规范模板，接入时需传 prompt= 参数。
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── 1. 系统 Prompt 正文 ───────────────────────────────────────────────────────
# 对应 Prompt 工程 7 段规范：Role / Task / Boundary / Constraints / Fallback / Output
REACT_SYSTEM = """You are a powerful AI assistant with access to multiple tools.
Use them step-by-step to answer the user's question accurately.

Available tools: {tools}
Tool names: {tool_names}

Guidelines:
- Think before acting. Use tools only when needed.
- Always verify results before presenting them.
- For calculations, use the calculator tool rather than guessing.
- For current events or facts, use the web search tool.
- For file operations, use the file tool with caution.
- Never fabricate information — if you don't know, search.
- Cite your sources when using search results.
"""

# ── 2. 完整 Prompt 模板 ───────────────────────────────────────────────────────
react_prompt = ChatPromptTemplate.from_messages([
    ("system", REACT_SYSTEM),                          # 系统指令 + 工具清单
    MessagesPlaceholder("chat_history", optional=True),  # 多轮对话历史（可选）
    ("human", "{input}"),                              # 当前用户问题
    MessagesPlaceholder("agent_scratchpad"),           # ReAct 中间步骤（工具调用记录）
])
