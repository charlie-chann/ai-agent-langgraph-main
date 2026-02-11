# agent.py — Agentic RAG with self-correction loop (LangGraph) v2.0
from __future__ import annotations

import json
import time
from typing import Generator, TypedDict, Annotated, List, Optional

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from loguru import logger

from config import settings, OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, TOP_K
from prompts.rag_prompts import rag_prompt, grade_prompt, rewrite_prompt
from tools.retriever import build_retriever, rerank_docs, get_vectorstore


# ── State ──────────────────────────────────────────────────────────────────────
class RAGState(TypedDict):
    question: str
    rewritten_question: str
    chat_history: List[BaseMessage]
    context_docs: List[Document]
    answer: str
    grade: str          # "yes" | "no"
    grade_reason: str
    iterations: int
    sources: List[str]
    latency_ms: float
    error: Optional[str]


MAX_ITERATIONS = settings.max_iterations


# ── LLM factory ───────────────────────────────────────────────────────────────
def _llm(streaming: bool = False, model: Optional[str] = None) -> ChatOllama:
    return ChatOllama(
        model=model or DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
        streaming=streaming,
    )


# ── Nodes ──────────────────────────────────────────────────────────────────────
def node_rewrite(state: RAGState) -> RAGState:
    """Rewrite query for better retrieval."""
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
    """Retrieve relevant documents."""
    try:
        # Use cached vectorstore
        vs = get_vectorstore()
        
        # Build retriever based on config
        retriever_fn = build_retriever()
        
        # Retrieve based on mode (callable returns docs directly)
        if callable(retriever_fn):
            docs = retriever_fn(state["rewritten_question"])
        else:
            # Fallback to vectorstore retriever
            retriever = vs.as_retriever(search_kwargs={"k": TOP_K})
            docs = retriever.invoke(state["rewritten_question"])
        
        # Rerank if enabled
        docs = rerank_docs(docs, state["rewritten_question"], top_n=TOP_K)
        
        state["context_docs"] = docs
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
    """Generate answer from context."""
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
    """Grade whether the answer is grounded in context."""
    context = "\n\n".join(d.page_content for d in state["context_docs"])
    
    try:
        chain = grade_prompt | _llm()
        result = chain.invoke({"context": context, "answer": state["answer"]})
        
        # Parse JSON response
        data = json.loads(result.content)
        state["grade"] = data.get("score", "yes")
        state["grade_reason"] = data.get("reason", "")
        
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        match = re.search(r'\{.*\}', result.content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                state["grade"] = data.get("score", "yes")
                state["grade_reason"] = data.get("reason", "")
            except:
                state["grade"] = "yes"  # Default to pass on parse error
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
    """Determine whether to retry with rewritten query."""
    if state["grade"] == "no" and state["iterations"] < MAX_ITERATIONS:
        logger.info(f"Retrying (iteration {state['iterations']}/{MAX_ITERATIONS})")
        return "rewrite"
    return END


# ── Build Graph ────────────────────────────────────────────────────────────────
def build_rag_graph():
    """Build the LangGraph workflow."""
    g = StateGraph(RAGState)
    
    # Add nodes
    g.add_node("rewrite", node_rewrite)
    g.add_node("retrieve", node_retrieve)
    g.add_node("generate", node_generate)
    g.add_node("grade", node_grade)
    
    # Set entry point
    g.set_entry_point("rewrite")
    
    # Linear flow
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "grade")
    
    # Conditional: retry on low grade
    g.add_conditional_edges("grade", _should_retry, {
        "rewrite": "rewrite",
        END: END
    })
    
    return g.compile()


# Singleton graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_rag_graph()
        logger.info("RAG Graph initialized")
    return _graph


# ── Public API ─────────────────────────────────────────────────────────────────
def ask(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    return_state: bool = False
) -> dict:
    """Non-streaming: returns full answer dict."""
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
    """Streaming version — yields answer tokens, then metadata JSON."""
    sources: List[str] = []
    
    # 1. rewrite + retrieve (non-streaming)
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
    
    # Stream tokens
    for chunk in chain.stream({
        "context": context or "(no context retrieved)",
        "question": question,
        "chat_history": chat_history or [],
    }):
        token = chunk.content
        full += token
        yield token
    
    # Yield metadata
    latency_ms = round((time.perf_counter() - t0) * 1000)
    meta = json.dumps({
        "sources": sources,
        "latency_ms": latency_ms,
        "docs_retrieved": len(context_docs),
        "__meta__": True
    })
    yield f"\n\n__META__{meta}"


# ── Utility Functions ────────────────────────────────────────────────────────
def reset_graph():
    """Reset the graph (useful for testing)."""
    global _graph
    _graph = None
    logger.info("RAG Graph reset")


def get_stats() -> dict:
    """Get system stats."""
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
