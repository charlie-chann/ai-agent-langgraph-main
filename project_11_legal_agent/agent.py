# agent.py — Legal Contract Review Agent
from __future__ import annotations

import time
from langchain_community.chat_models import ChatOllama
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from prompts.legal_prompts import LEGAL_ANALYSIS_PROMPT, CLAUSE_REWRITE_PROMPT
from tools.contract_analyzer import analyze_contract, generate_review_report, ContractAnalysisResult
from tools.clause_extractor import extract_parties, sanitize_contract_input


def _llm():
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def review_contract(contract_text: str, contract_type: str = "通用合同") -> dict:
    """
    完整合同审查流程：
    1. 规则引擎快速扫描风险
    2. 提取当事人信息
    3. LLM 深度分析
    4. 生成综合报告
    """
    t0 = time.perf_counter()

    # 1. 输入清洗
    contract_text = sanitize_contract_input(contract_text)
    logger.info(f"[review_contract] type={contract_type}, chars={len(contract_text)}")

    # 2. 规则引擎分析
    rule_result = analyze_contract(contract_text, contract_type)
    parties = extract_parties(contract_text)
    rule_report = generate_review_report(rule_result, contract_type)

    # 3. LLM 深度分析（基于规则结果）
    rule_summary = f"发现 {len(rule_result.high_risks)} 条高风险、{len(rule_result.medium_risks)} 条中风险、{len(rule_result.low_risks)} 条低风险条款"

    llm_analysis = ""
    try:
        chain = LEGAL_ANALYSIS_PROMPT | _llm()
        for chunk in chain.stream({
            "contract_type": contract_type,
            "contract_text": contract_text[:8000],
            "rule_findings": rule_summary,
        }):
            llm_analysis += chunk.content
    except Exception as e:
        logger.warning(f"LLM 分析失败（使用规则报告）: {e}")
        llm_analysis = rule_report

    elapsed = round((time.perf_counter() - t0) * 1000)
    logger.info(f"[review_contract] 完成，耗时 {elapsed}ms")

    return {
        "rule_analysis": rule_result.to_dict(),
        "parties": {
            "party_a": parties.party_a,
            "party_b": parties.party_b,
            "amount": parties.contract_amount,
            "period": parties.contract_period,
            "dispute_resolution": parties.dispute_resolution,
        },
        "rule_report": rule_report,
        "llm_analysis": llm_analysis,
        "total_latency_ms": elapsed,
    }


def rewrite_clause(clause_text: str, risk_description: str) -> str:
    """将有风险的条款重写为更公平的版本（流式）。"""
    clause_text = sanitize_contract_input(clause_text)
    chain = CLAUSE_REWRITE_PROMPT | _llm()
    result = ""
    for chunk in chain.stream({"original_clause": clause_text, "risk_description": risk_description}):
        result += chunk.content
    return result


def stream_review(contract_text: str, contract_type: str = "通用合同"):
    """流式审查合同，yield 进度事件。"""
    contract_text = sanitize_contract_input(contract_text)

    # Step 1: 规则分析（快速）
    yield {"step": "rule_analysis", "message": "⚡ 规则引擎扫描中..."}
    rule_result = analyze_contract(contract_text, contract_type)
    parties = extract_parties(contract_text)
    yield {
        "step": "rule_done",
        "high_risks": len(rule_result.high_risks),
        "medium_risks": len(rule_result.medium_risks),
        "risk_score": rule_result.total_risk_score,
        "rule_report": generate_review_report(rule_result, contract_type),
    }

    # Step 2: LLM 深度分析（流式）
    yield {"step": "llm_start", "message": "🤖 AI 法律深度分析中..."}
    try:
        chain = LEGAL_ANALYSIS_PROMPT | _llm()
        llm_text = ""
        for chunk in chain.stream({
            "contract_type": contract_type,
            "contract_text": contract_text[:8000],
            "rule_findings": f"规则发现 {len(rule_result.high_risks)} 条高风险",
        }):
            llm_text += chunk.content
            yield {"step": "llm_chunk", "content": chunk.content}
        yield {"step": "llm_done", "full_analysis": llm_text}
    except Exception as e:
        yield {"step": "llm_error", "error": str(e)}
