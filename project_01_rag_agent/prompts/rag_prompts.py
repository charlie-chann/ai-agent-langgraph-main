"""
prompts/rag_prompts.py — LLM 提示词模板

【职责】
定义 RAG 流程中三个关键环节的 Prompt，与业务逻辑解耦。

【设计原因】
1. Prompt 单独成文件：方便产品/运营调文案，不用改 agent.py 核心逻辑
2. 使用 ChatPromptTemplate：LangChain 标准格式，可复用、可组合、可版本管理
3. 三个 Prompt 对应 Agent 三个 LLM 调用点：生成 / 评分 / 改写
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── 1. RAG 回答生成 Prompt ────────────────────────────────────────────────────
# 核心约束：只能依据检索到的 context 回答，防止模型「幻觉」编造
# 要求标注来源，满足企业审计「答案可追溯」需求
RAG_SYSTEM = """You are a precise enterprise knowledge-base assistant.
Answer the user's question using ONLY the retrieved context below.
If the context does not contain enough information, say so honestly.
Always cite the source document(s) at the end of your answer like:
  [Source: <filename>, page <n>]

Retrieved context:
{context}
"""

rag_prompt = ChatPromptTemplate.from_messages([
    ("system", RAG_SYSTEM),
    # MessagesPlaceholder：支持多轮对话历史，占位符名 chat_history
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{question}"),
])

# ── 2. 答案质量评分 Prompt（Agentic RAG 的自校正环节）────────────────────────
# 让 LLM 判断：生成的 answer 是否真正 grounded 于 context
# 输出 JSON 便于程序解析；score=no 时会触发重新检索
GRADE_SYSTEM = """You are a grader. Assess whether the following answer is grounded
in the provided context. Reply with JSON only: {{"score": "yes"|"no", "reason": "..."}}

Context:
{context}

Answer:
{answer}
"""

grade_prompt = ChatPromptTemplate.from_messages([
    ("system", GRADE_SYSTEM),
])

# ── 3. 查询改写 Prompt（检索失败时的补救）────────────────────────────────────
# 当第一次检索+生成+评分不通过时，把用户问题改写成更「检索友好」的表述
# 例如：口语化问题 → 含关键词的完整问句
REWRITE_SYSTEM = """You are a query optimizer for a vector search engine.
Rewrite the user's question to be more specific and retrieval-friendly.
Return ONLY the rewritten question, no explanation.
"""

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", REWRITE_SYSTEM),
    ("human", "{question}"),
])
