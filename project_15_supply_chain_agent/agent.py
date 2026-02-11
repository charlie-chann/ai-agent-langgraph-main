# agent.py — 供应链/物流优化 Agent
from __future__ import annotations

import re
import time
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.inventory_tool import InventoryItem, analyze_inventory, forecast_demand
from tools.route_optimizer import DeliveryStop, optimize_route, detect_delay_risk


_SYSTEM_PROMPT = """你是一个专业的供应链和物流优化 AI 助手。你的核心职责：
1. 分析库存状态，识别缺货风险，生成补货建议
2. 优化配送路径，降低物流成本
3. 预测需求趋势，提前预警供应链风险
4. 分析供应链异常，提供应对建议

回复简洁专业，以数据为依据，给出可操作的建议。
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize_input(text: str) -> str:
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text[:3000]


def run_inventory_analysis(items_data: list[dict]) -> dict:
    """执行库存分析。"""
    items = []
    for d in items_data:
        try:
            item = InventoryItem(
                sku=str(d.get("sku", ""))[:20],
                name=str(d.get("name", ""))[:50],
                current_stock=int(d.get("current_stock", 0)),
                daily_demand=float(d.get("daily_demand", 1)),
                unit_cost=float(d.get("unit_cost", 0)),
                lead_time_days=int(d.get("lead_time_days", 3)),
            )
            items.append(item)
        except (ValueError, TypeError) as e:
            logger.warning(f"跳过无效库存记录: {e}")
    t0 = time.perf_counter()
    result = analyze_inventory(items)
    logger.info(f"库存分析完成 | SKU数: {len(items)} | 耗时: {time.perf_counter()-t0:.2f}s")
    return result


def run_route_optimization(depot_data: dict, stops_data: list[dict]) -> dict:
    """执行路径优化。"""
    depot = DeliveryStop(
        stop_id=str(depot_data.get("id", "DEPOT")),
        name=str(depot_data.get("name", "仓库")),
        lat=float(depot_data.get("lat", 0)),
        lon=float(depot_data.get("lon", 0)),
    )
    stops = []
    for d in stops_data:
        try:
            stops.append(DeliveryStop(
                stop_id=str(d.get("id", ""))[:20],
                name=str(d.get("name", ""))[:50],
                lat=float(d.get("lat", 0)),
                lon=float(d.get("lon", 0)),
                demand=float(d.get("demand", 0)),
            ))
        except (ValueError, TypeError):
            continue
    t0 = time.perf_counter()
    route = optimize_route(depot, stops)
    risks = detect_delay_risk(stops, route)
    logger.info(f"路径优化完成 | 站点: {len(stops)} | 距离: {route.total_distance_km:.1f}km | 耗时: {time.perf_counter()-t0:.2f}s")
    return {**route.to_dict(), "delay_risks": risks}


def stream_chat(user_message: str, history: list[dict] | None = None):
    """流式对话生成器。"""
    user_message = _sanitize_input(user_message)
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT)]
    for h in (history or []):
        if h.get("role") == "user":
            from langchain_core.messages import HumanMessage
            messages.append(HumanMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))
    for chunk in llm.stream(messages):
        yield chunk.content
