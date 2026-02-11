# tools/price_monitor.py — 竞品价格监控工具
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import date

from config import PRICE_ALERT_PCT, MAX_COMPETITORS


@dataclass
class Product:
    """商品数据类。"""
    product_id: str
    name: str
    category: str
    our_price: float
    cost: float = 0.0
    description: str = ""

    @property
    def margin_pct(self) -> float:
        return ((self.our_price - self.cost) / self.our_price * 100) if self.our_price > 0 else 0


@dataclass
class CompetitorPrice:
    """竞品价格记录。"""
    competitor_name: str
    product_id: str
    price: float
    date: str = field(default_factory=lambda: str(date.today()))
    url: str = ""


@dataclass
class PriceAlert:
    """价格预警。"""
    product_id: str
    alert_type: str   # "undercut" | "opportunity" | "significant_change"
    competitor: str
    their_price: float
    our_price: float
    diff_pct: float
    action: str

    def to_dict(self) -> dict:
        return {
            "商品ID": self.product_id,
            "预警类型": self.alert_type,
            "竞争对手": self.competitor,
            "对手价格": f"¥{self.their_price:.2f}",
            "我方价格": f"¥{self.our_price:.2f}",
            "价差(%)": round(self.diff_pct, 1),
            "建议行动": self.action,
        }


def analyze_competitor_prices(product: Product,
                               competitor_prices: list[CompetitorPrice]) -> dict:
    """
    分析竞品价格，生成定价建议。

    Args:
        product: 我方商品信息
        competitor_prices: 竞品价格列表

    Returns:
        dict: 分析报告
    """
    if not competitor_prices:
        return {"alerts": [], "recommendation": "暂无竞品数据", "suggested_price": product.our_price}

    prices = [cp.price for cp in competitor_prices[:MAX_COMPETITORS]]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    alerts = []
    for cp in competitor_prices[:MAX_COMPETITORS]:
        diff_pct = (product.our_price - cp.price) / cp.price * 100  # 正数=我方贵

        if diff_pct > PRICE_ALERT_PCT:
            # 我方价格明显高于竞品
            alerts.append(PriceAlert(
                product_id=product.product_id,
                alert_type="undercut",
                competitor=cp.competitor_name,
                their_price=cp.price,
                our_price=product.our_price,
                diff_pct=diff_pct,
                action=f"考虑降价至 ¥{cp.price * 1.05:.2f} 左右以维持竞争力",
            ))
        elif diff_pct < -PRICE_ALERT_PCT:
            # 对手价格明显高于我方
            alerts.append(PriceAlert(
                product_id=product.product_id,
                alert_type="opportunity",
                competitor=cp.competitor_name,
                their_price=cp.price,
                our_price=product.our_price,
                diff_pct=abs(diff_pct),
                action=f"可适当提价至 ¥{min(cp.price * 0.97, product.our_price * 1.1):.2f}，提升利润率",
            ))

    # 定价建议
    if product.our_price > avg_price * 1.1:
        suggested = round(avg_price * 1.05, 2)
        recommendation = f"价格偏高，建议调整为 ¥{suggested}（市场均价 ¥{avg_price:.2f}）"
    elif product.our_price < avg_price * 0.9:
        suggested = round(avg_price * 0.95, 2)
        recommendation = f"价格偏低，可适度提价至 ¥{suggested}，增加利润空间"
    else:
        suggested = product.our_price
        recommendation = f"价格合理，处于市场均值（¥{avg_price:.2f}）附近"

    # 保证建议价格不低于成本
    if product.cost > 0:
        suggested = max(suggested, product.cost * 1.1)

    return {
        "商品": product.name,
        "竞品数量": len(competitor_prices),
        "竞品最低价": f"¥{min_price:.2f}",
        "竞品均价": f"¥{avg_price:.2f}",
        "竞品最高价": f"¥{max_price:.2f}",
        "当前价格": f"¥{product.our_price:.2f}",
        "建议价格": f"¥{suggested:.2f}",
        "定价建议": recommendation,
        "预警": [a.to_dict() for a in alerts],
    }


def generate_product_description(product: Product) -> str:
    """
    基于商品信息生成 SEO 友好的商品描述（模板驱动）。
    """
    from config import DESC_MAX_LENGTH

    name = re.sub(r'[<>"\']', '', product.name)[:50]
    category = re.sub(r'[<>"\']', '', product.category)[:30]

    templates = [
        f"【{name}】{category}领域的优质之选！精心打造，品质保证。无论您是初次尝试还是资深用户，{name}都能满足您的需求。立即购买，享受极致体验！",
        f"专业{category}推荐 ✓ {name}，采用高品质原材料，严格品控，每一件都经过精挑细选。现货发售，快速发货，支持7天无理由退换货。",
        f"🌟 {name} | {category}爆款 🌟 数千好评，用户高度认可！轻松上手，效果显著。[限时特价]今日下单享优先发货！",
    ]

    # 简单循环选择（避免随机种子问题）
    desc = templates[len(name) % len(templates)]
    if len(desc) > DESC_MAX_LENGTH:
        desc = desc[:DESC_MAX_LENGTH - 3] + "..."
    return desc
