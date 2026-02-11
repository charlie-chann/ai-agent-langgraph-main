"""
agent.py — Agentic RAG 核心（LangGraph 状态机）

【职责】
编排完整的问答流程：改写查询 → 检索 → 生成 → 评分 → （不满意则重试）

【与普通 RAG 的区别】
普通 RAG：检索一次 → 生成一次 → 结束。
Agentic RAG：生成后用 LLM 评分；若答案未 grounded 于文档，改写问题重新检索（最多 max_iterations 次）。

【为什么用 LangGraph】
1. 状态 RAGState 在各节点间传递，逻辑清晰
2. conditional_edges 实现「评分不通过则回到 rewrite」的循环
3. 比手写 if/while 更易扩展（例如未来加「多文档路由」节点）

【对外接口】
- ask()：同步，返回完整 dict（含 sources、latency）
- ask_stream()：流式，逐 token yield，末尾附带 __META__ 元数据
"""
from __future__ import annotations

import json
import time
from typing import Generator, TypedDict, Annotated, List, Optional

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from loguru import logger

from config import settings, OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, TOP_K
from prompts.rag_prompts import rag_prompt, grade_prompt, rewrite_prompt
from tools.retriever import build_retriever, rerank_docs, get_vectorstore


class RAGState(TypedDict):
    """
    LangGraph 全局状态 — 每个节点读取并更新其中的字段。

    所有字段在一次 invoke 中贯穿 rewrite → retrieve → generate → grade。
    """
    question: str              # 用户原始问题
    rewritten_question: str    # 改写后用于检索的问题（首次等于原问题）
    chat_history: List[BaseMessage]  # 多轮对话历史
    context_docs: List[Document]     # 检索到的文档片段
    answer: str                # LLM 生成的回答
    grade: str                   # 评分结果："yes" | "no"
    grade_reason: str          # 评分理由（调试用）
    iterations: int            # 已完成的评分轮数（控制重试上限）
    sources: List[str]         # 引用来源文件名列表
    latency_ms: float          # 生成阶段耗时（毫秒）
    error: Optional[str]       # 检索等环节的错误信息


MAX_ITERATIONS = settings.max_iterations


def _llm(streaming: bool = False, model: Optional[str] = None) -> ChatOllama:
    """
    创建 Ollama 聊天模型实例。

    streaming=True 用于 ask_stream 逐字输出；
    temperature 来自 config，RAG 场景偏低以保证稳定性。
    """
    return ChatOllama(
        model=model or DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
        streaming=streaming,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LangGraph 节点 — 每个函数是一个「处理步骤」
# ══════════════════════════════════════════════════════════════════════════════

def node_rewrite(state: RAGState) -> RAGState:
    """
    节点 1：查询改写。

    - 第一次进入（iterations=0）：不改写，直接用原问题检索（节省一次 LLM 调用）
    - 重试进入：说明上次评分 no，用 rewrite_prompt 生成更利于检索的问法
    """
    question = state["question"]
    iterations = state.get("iterations", 0)

    if iterations == 0:
        state["rewritten_question"] = question
        return state

    try:
        chain = rewrite_prompt | _llm()
        result = chain.invoke({"question": question})
        state["rewritten_question"] = result.content.strip()
        logger.info(f"Rewritten: {state['rewritten_question']}")
    except Exception as e:
        logger.warning(f"Rewrite failed: {e}, using original question")
        state["rewritten_question"] = question

    return state


def node_retrieve(state: RAGState) -> RAGState:
    """
    节点 2：从知识库检索相关文档。

    流程：build_retriever() 按配置选 hybrid/dense/sparse
         → 用 rewritten_question 检索
         → rerank_docs 精排
         → 写入 context_docs 和 sources
    """
    try:
        vs = get_vectorstore()
        retriever_fn = build_retriever()

        if callable(retriever_fn):
            docs = retriever_fn(state["rewritten_question"])
        else:
            # 兜底：直接使用 Chroma 内置 retriever
            retriever = vs.as_retriever(search_kwargs={"k": TOP_K})
            docs = retriever.invoke(state["rewritten_question"])

        docs = rerank_docs(docs, state["rewritten_question"], top_n=TOP_K)

        state["context_docs"] = docs
        # 去重后的来源文件名，供 UI/API 展示引用
        state["sources"] = list({d.metadata.get("source", "unknown") for d in docs})
        state["error"] = None
        logger.info(f"Retrieved {len(docs)} docs")

    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        state["context_docs"] = []
        state["sources"] = []
        state["error"] = f"Retrieval error: {str(e)}"

    return state


def node_generate(state: RAGState) -> RAGState:
    """
    节点 3：基于检索上下文生成回答。

    多个 chunk 用 --- 分隔拼成 context，注入 rag_prompt。
    若无检索结果仍调用 LLM，Prompt 要求诚实说明「文档中无相关信息」。
    """
    t0 = time.perf_counter()

    context = "\n\n---\n\n".join(d.page_content for d in state["context_docs"])

    try:
        chain = rag_prompt | _llm()
        result = chain.invoke({
            "context": context or "(no context retrieved)",
            "question": state["question"],
            "chat_history": state.get("chat_history", []),
        })
        state["answer"] = result.content
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        state["answer"] = f"I apologize, but I encountered an error: {str(e)}"

    state["latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return state


def node_grade(state: RAGState) -> RAGState:
    """
    节点 4：答案质量评分（Agentic 关键步骤）。

    用 grade_prompt 让 LLM 判断 answer 是否 grounded 于 context。
    小模型可能返回非标准 JSON，故有多层解析兜底；
    解析失败时默认 pass（yes），避免无限重试卡死用户。
    """
    context = "\n\n".join(d.page_content for d in state["context_docs"])

    try:
        chain = grade_prompt | _llm()
        result = chain.invoke({"context": context, "answer": state["answer"]})

        data = json.loads(result.content)
        state["grade"] = data.get("score", "yes")
        state["grade_reason"] = data.get("reason", "")

    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', result.content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                state["grade"] = data.get("score", "yes")
                state["grade_reason"] = data.get("reason", "")
            except:
                state["grade"] = "yes"
                state["grade_reason"] = "Parse error, defaulting to pass"
        else:
            state["grade"] = "yes"
            state["grade_reason"] = "Grading failed, defaulting to pass"
    except Exception as e:
        logger.warning(f"Grading failed: {e}, defaulting to pass")
        state["grade"] = "yes"
        state["grade_reason"] = f"Error: {str(e)}"

    state["iterations"] = state.get("iterations", 0) + 1
    logger.info(f"Grade: {state['grade']} (iter={state['iterations']}) - {state['grade_reason']}")
    return state


def _should_retry(state: RAGState) -> str:
    """
    条件边路由函数：决定 grade 之后是 END 还是回到 rewrite。

    grade=no 且 iterations < MAX_ITERATIONS → 重试
    否则 → END
    """
    if state["grade"] == "no" and state["iterations"] < MAX_ITERATIONS:
        logger.info(f"Retrying (iteration {state['iterations']}/{MAX_ITERATIONS})")
        return "rewrite"
    return END


def build_rag_graph():
    """
    构建并编译 LangGraph 工作流。

    图结构：
      rewrite → retrieve → generate → grade
                                        ↓ (条件)
                              no 且未超限 → rewrite
                              否则 → END
    """
    g = StateGraph(RAGState)

    g.add_node("rewrite", node_rewrite)
    g.add_node("retrieve", node_retrieve)
    g.add_node("generate", node_generate)
    g.add_node("grade", node_grade)

    g.set_entry_point("rewrite")

    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "grade")

    g.add_conditional_edges("grade", _should_retry, {
        "rewrite": "rewrite",
        END: END
    })

    return g.compile()


_graph = None  # 编译后的图单例，避免重复 build


def get_graph():
    """懒加载获取已编译的 RAG 图。"""
    global _graph
    if _graph is None:
        _graph = build_rag_graph()
        logger.info("RAG Graph initialized")
    return _graph


# ══════════════════════════════════════════════════════════════════════════════
# 对外 API — 供 app.py / api.py / 测试 调用
# ══════════════════════════════════════════════════════════════════════════════

def ask(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    return_state: bool = False
) -> dict:
    """
    同步问答：跑完整个 LangGraph（含可能的重试循环），返回结构化结果。

    适用于 API /chat、脚本测试。
    """
    state = get_graph().invoke({
        "question": question,
        "rewritten_question": question,
        "chat_history": chat_history or [],
        "iterations": 0,
    })

    result = {
        "answer": state["answer"],
        "sources": state["sources"],
        "latency_ms": state.get("latency_ms", 0),
        "iterations": state.get("iterations", 1),
        "grade": state.get("grade", "unknown"),
        "error": state.get("error"),
    }

    if return_state:
        result["state"] = state

    return result


def ask_stream(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None
) -> Generator[str, None, None]:
    """
    流式问答：检索完成后逐 token 输出，体验更流畅。

    【设计取舍】
    流式路径**不跑完整的 grade 重试循环**（rewrite+retrieve 只做一轮），
    否则用户需等多轮检索才能看到第一个字。
    适合 Streamlit UI；要严格自校正请用 ask()。

    最后一个 yield 为 \\n\\n__META__{json}，携带 sources 和 latency。
    """
    sources: List[str] = []

    temp_state: RAGState = {
        "question": question,
        "rewritten_question": question,
        "iterations": 0,
        "chat_history": chat_history or [],
    }
    node_rewrite(temp_state)
    node_retrieve(temp_state)

    context_docs = temp_state.get("context_docs", [])
    sources = temp_state.get("sources", [])

    context = "\n\n---\n\n".join(d.page_content for d in context_docs)
    chain = rag_prompt | _llm(streaming=True)

    t0 = time.perf_counter()
    full = ""

    for chunk in chain.stream({
        "context": context or "(no context retrieved)",
        "question": question,
        "chat_history": chat_history or [],
    }):
        token = chunk.content
        full += token
        yield token

    latency_ms = round((time.perf_counter() - t0) * 1000)
    meta = json.dumps({
        "sources": sources,
        "latency_ms": latency_ms,
        "docs_retrieved": len(context_docs),
        "__meta__": True
    })
    yield f"\n\n__META__{meta}"


def reset_graph():
    """测试用：重置图单例，配置变更后可重新 build。"""
    global _graph
    _graph = None
    logger.info("RAG Graph reset")


def get_stats() -> dict:
    """返回当前检索层状态，便于监控与调试。"""
    from tools.retriever import get_vectorstore, _chunks
    try:
        vs = get_vectorstore()
        doc_count = vs._collection.count()
    except:
        doc_count = 0

    return {
        "chunks_loaded": len(_chunks),
        "documents_indexed": doc_count,
        "retrieval_mode": settings.retrieval_mode,
        "rerank_enabled": settings.rerank_enabled,
        "max_iterations": MAX_ITERATIONS,
    }
