"""
graph/nodes.py — LangGraph 节点实现

【职责】
实现 RAG 工作流中每个处理步骤：安全守卫 → 查询改写 → 检索 → 生成 → 评分 → HITL 门控。

【设计原因】
1. 一节点一函数：与 LangGraph add_node 一一对应，职责单一、便于单测与替换
2. 节点只读写 RagState：不持有全局可变状态，图编译后可并发 invoke（不同 thread_id）
3. LLM 调用统一走 _invoke_chain + run_with_timeout：超时与熔断策略集中，避免各节点重复封装
4. fail-open / fail-safe 分层：guard/grade 解析失败时默认放行；retrieve/generate 失败时写入 error 或降级摘要
"""
from __future__ import annotations

import json
import re
import time
from typing import List

from langchain_core.messages import AIMessage
from loguru import logger

from app.core.config import settings
from app.core.compression import trim_context_chunks
from app.core.timeouts import run_with_timeout
from app.agent.graphs.rag.state import RagState
from app.agent.prompts.rag import grade_prompt, guard_prompt, rag_prompt, rewrite_prompt
from app.infrastructure.providers.factory import ModelRole, get_chat_model
from app.knowledge.conflict import detect_conflicts, format_conflicts
from app.knowledge.retriever import retrieve_with_kg


# ══════════════════════════════════════════════════════════════════════════════
# 内部工具 — LLM 链调用
# ══════════════════════════════════════════════════════════════════════════════

def _invoke_chain(prompt, inputs: dict, *, label: str, role: ModelRole = "aux") -> str:
    """
    执行 prompt | chat_model 链并返回 strip 后的文本内容。

    guard/rewrite/grade 默认 role=aux（小模型）；generate 节点单独传 role=generate。
    """
    chain = prompt | get_chat_model(role=role)
    result = run_with_timeout(lambda: chain.invoke(inputs), settings.llm_timeout, label=label)
    return result.content.strip()


# ══════════════════════════════════════════════════════════════════════════════
# LangGraph 节点 — 每个函数是一个「处理步骤」
# ══════════════════════════════════════════════════════════════════════════════

def node_guard(state: RagState) -> RagState:
    """
    节点 0：入口安全守卫 + HITL 风险标记。

    - 根据 hitl_risk_keywords 判断是否需人工审批（hitl_required）
    - 调用 guard_prompt 检测 jailbreak / 凭证窃取等，blocked 时直接写入 answer 并短路后续节点
    - guard LLM 异常时 fail-open：记录日志但不阻断流程（企业内网场景优先可用性）
    """
    question = state["question"]
    # 从配置读取逗号分隔的风险词，转小写后做子串匹配
    risk_words = [w.strip() for w in settings.hitl_risk_keywords.split(",") if w.strip()]
    hitl = settings.hitl_enabled and any(w in question.lower() for w in risk_words)
    state["hitl_required"] = hitl
    state["hitl_approved"] = state.get("hitl_approved", False)

    try:
        raw = _invoke_chain(guard_prompt, {"question": question}, label="guard")
        data = json.loads(raw)
        if data.get("blocked"):
            # 拦截：设置 error=blocked，route_after_guard 将直接 END
            state["answer"] = f"I cannot process this request: {data.get('reason', 'blocked')}"
            state["grade"] = "yes"          # 避免 grade 节点再次触发重试
            state["error"] = "blocked"
            return state
    except Exception as e:
        logger.warning(f"Guard failed open: {e}")
    return state


def node_rewrite(state: RagState) -> RagState:
    """
    节点 1：查询改写。

    - 第一次进入（iterations=0）：不改写，直接用原问题检索（节省一次 LLM 调用）
    - 重试进入：说明上次 grade=no，用 rewrite_prompt 生成更利于向量检索的问法
    - 改写失败时回退到原问题，保证 retrieve 仍可执行
    """
    question = state["question"]
    if state.get("iterations", 0) == 0:
        state["rewritten_question"] = question
        return state
    try:
        state["rewritten_question"] = _invoke_chain(rewrite_prompt, {"question": question}, label="rewrite")
    except Exception as e:
        logger.warning(f"Rewrite fallback: {e}")
        state["rewritten_question"] = question
    return state


def node_retrieve(state: RagState) -> RagState:
    """
    节点 2：混合检索 + 知识图谱 + 冲突检测。

    流程：retrieve_with_kg(rewritten_question, user_roles)
         → 写入 context_docs / kg_context / sources
         → detect_conflicts 检测多源矛盾并 format 为可读文本
    RBAC：user_roles 传入 retriever，过滤无权限文档。
    """
    try:
        roles = state.get("user_roles") or []
        docs, kg_ctx = retrieve_with_kg(state["rewritten_question"], user_roles=roles)
        state["context_docs"] = docs
        state["kg_context"] = kg_ctx
        # 去重来源，供前端展示「引用自哪些文件」
        state["sources"] = list({d.metadata.get("source", "unknown") for d in docs})
        conflicts = detect_conflicts(docs)
        state["conflicts"] = format_conflicts(conflicts)
        state["error"] = None
    except Exception as e:
        logger.error(f"Retrieve failed: {e}")
        # 检索失败：清空上下文，error 供 generate 降级或 API 返回
        state["context_docs"] = []
        state["kg_context"] = ""
        state["sources"] = []
        state["conflicts"] = ""
        state["error"] = str(e)
    return state


def node_generate(state: RagState) -> RagState:
    """
    节点 3：基于检索上下文 + KG + 冲突摘要生成回答。

    - trim_context_chunks 压缩 context，避免超出模型窗口
    - 注入 rag_prompt：要求仅依据 context/kg 回答并标注来源
    - LLM 失败且有 chunks 时：降级展示首段检索摘要；无 chunks 时返回服务不可用
    """
    if state.get("error") == "blocked":
        return state

    t0 = time.perf_counter()
    chunks = [d.page_content for d in state.get("context_docs", [])]
    context = trim_context_chunks(chunks)

    try:
        writer = None
        try:
            from langgraph.config import get_stream_writer

            writer = get_stream_writer()
        except Exception:
            writer = None

        inputs = {
            "context": context or "(no context)",
            "kg_context": state.get("kg_context") or "(none)",
            "conflicts": state.get("conflicts") or "",
            "question": state["question"],
            "chat_history": state.get("chat_history") or [],
        }
        if writer is not None:
            chain = rag_prompt | get_chat_model(streaming=True, role="generate")
            parts: list[str] = []
            for chunk in chain.stream(inputs):
                token = getattr(chunk, "content", "") or ""
                if token:
                    parts.append(token)
                    writer({"type": "token", "content": token})
            state["answer"] = "".join(parts)
        else:
            state["answer"] = _invoke_chain(rag_prompt, inputs, label="generate", role="generate")
    except Exception as e:
        logger.error(f"Generate failed: {e}")
        if chunks:
            # 有检索结果但生成失败：展示首 chunk 摘要作为兜底
            state["answer"] = "Based on retrieved documents (generation degraded):\n" + chunks[0][:500]
            state["disclaimer"] = "LLM generation failed; showing retrieval summary."
        else:
            state["answer"] = f"Service temporarily unavailable: {e}"
            state["error"] = str(e)

    state["latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return state


def node_grade(state: RagState) -> RagState:
    """
    节点 4：答案质量评分（Agentic RAG 自校正环节）。

    用 grade_prompt 判断 answer 是否 grounded 于 context。
    小模型可能返回非标准 JSON，故 regex 提取 {...} 兜底；
    解析/调用失败时默认 yes（fail-open），避免无限重试。
    达到 max_iterations 仍 no 时附加 disclaimer 提醒用户自行核实。
    """
    if state.get("error") == "blocked":
        return state

    context = "\n\n".join(d.page_content for d in state.get("context_docs", []))
    try:
        raw = _invoke_chain(grade_prompt, {"context": context, "answer": state["answer"]}, label="grade")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 非纯 JSON 响应：尝试从文本中提取第一个 JSON 对象
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {"score": "yes", "reason": "parse fallback"}
        state["grade"] = data.get("score", "yes")
        state["grade_reason"] = data.get("reason", "")
    except Exception as e:
        logger.warning(f"Grade fail-open: {e}")
        state["grade"] = "yes"
        state["grade_reason"] = str(e)

    state["iterations"] = state.get("iterations", 0) + 1

    if state["grade"] == "no" and state["iterations"] >= settings.max_iterations:
        state["disclaimer"] = "Answer may not be fully grounded; please verify sources."

    return state


def node_hitl_gate(state: RagState) -> RagState:
    """
    节点 HITL：高风险查询的人工审批门控（骨架实现）。

    当 hitl_required 且尚未 hitl_approved 时，设置等待审批的占位 answer。
    配合 builder 的 interrupt_before=["hitl_gate"] + checkpointer：
    图在此节点前暂停，人工批准后带 hitl_approved=True 恢复执行。
    """
    if state.get("hitl_required") and not state.get("hitl_approved"):
        state["answer"] = state.get("answer") or "Awaiting human approval for high-risk query."
    return state
