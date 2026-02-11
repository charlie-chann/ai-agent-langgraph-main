# prompts/rag_prompts.py
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── RAG Answer Prompt ──────────────────────────────────────────────────────────
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
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{question}"),
])

# ── Self-Correction / Grading Prompt ──────────────────────────────────────────
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

# ── Query Rewrite Prompt ───────────────────────────────────────────────────────
REWRITE_SYSTEM = """You are a query optimizer for a vector search engine.
Rewrite the user's question to be more specific and retrieval-friendly.
Return ONLY the rewritten question, no explanation.
"""

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", REWRITE_SYSTEM),
    ("human", "{question}"),
])
