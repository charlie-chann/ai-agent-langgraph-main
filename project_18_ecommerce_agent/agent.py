# agent.py — 电商自动化 Agent
from __future__ import annotations
import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.price_monitor import Product, CompetitorPrice, analyze_competitor_prices, generate_product_description

_SYSTEM_PROMPT = "你是一个专业的电商 AI 助手，帮助卖家做竞品分析、定价策略和商品文案优化。"

def _llm(): return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)
def _sanitize(t): return re.sub(r'[\x00-\x1f\x7f]', '', str(t))[:3000]

def run_price_analysis(product_data: dict, competitor_prices: list[dict]) -> dict:
    product = Product(
        product_id=str(product_data.get("id", "P001")),
        name=_sanitize(product_data.get("name", "")),
        category=_sanitize(product_data.get("category", "")),
        our_price=float(product_data.get("price", 0)),
        cost=float(product_data.get("cost", 0)),
    )
    comps = [CompetitorPrice(competitor_name=c.get("name", ""), product_id=product.product_id,
                              price=float(c.get("price", 0))) for c in competitor_prices]
    return analyze_competitor_prices(product, comps)

def run_generate_desc(product_data: dict) -> str:
    product = Product(
        product_id=str(product_data.get("id", "P001")),
        name=_sanitize(product_data.get("name", "")),
        category=_sanitize(product_data.get("category", "")),
        our_price=float(product_data.get("price", 0)),
    )
    return generate_product_description(product)

def stream_chat(user_message: str, history: list | None = None):
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=_sanitize(user_message))]
    for chunk in llm.stream(messages):
        yield chunk.content
