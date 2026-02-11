# tools/inventory_tool.py — 库存管理与预测工具
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from config import STOCK_LOW_DAYS, STOCK_CRITICAL_DAYS


@dataclass
class InventoryItem:
    """库存记录数据类。"""
    sku: str
    name: str
    current_stock: int      # 当前库存量（件）
    daily_demand: float     # 日均需求量
    unit_cost: float        # 单位成本（元）
    lead_time_days: int     # 补货前置时间（天）
    reorder_point: int = 0  # 再订购点

    def __post_init__(self):
        # 自动计算再订购点 = 前置时间内需求 + 安全库存（3天）
        safety = math.ceil(self.daily_demand * 3)
        self.reorder_point = math.ceil(self.daily_demand * self.lead_time_days) + safety

    @property
    def days_of_stock(self) -> float:
        """当前库存可以支撑的天数。"""
        return self.current_stock / self.daily_demand if self.daily_demand > 0 else float('inf')

    @property
    def status(self) -> str:
        days = self.days_of_stock
        if days <= STOCK_CRITICAL_DAYS:
            return "critical"
        elif days <= STOCK_LOW_DAYS:
            return "low"
        else:
            return "normal"


@dataclass
class ReplenishmentOrder:
    """补货建议。"""
    sku: str
    order_qty: int
    urgency: str              # "critical" | "standard"
    estimated_cost: float
    earliest_arrival: str     # 预计到货日期

    def to_dict(self) -> dict:
        return {
            "SKU": self.sku,
            "建议补货量": self.order_qty,
            "紧急程度": self.urgency,
            "预计费用": f"¥{self.estimated_cost:.2f}",
            "预计到货": self.earliest_arrival,
        }


def analyze_inventory(items: list[InventoryItem]) -> dict:
    """
    分析库存状态，生成补货建议。

    Returns:
        dict: 包含 summary、alerts、orders
    """
    alerts = []
    orders = []
    total_value = 0.0

    for item in items:
        total_value += item.current_stock * item.unit_cost
        if item.status in ("critical", "low"):
            alerts.append({
                "sku": item.sku,
                "name": item.name,
                "status": item.status,
                "days_remaining": round(item.days_of_stock, 1),
                "message": f"库存不足 {item.days_of_stock:.0f} 天，需立即补货" if item.status == "critical"
                           else f"库存低于{STOCK_LOW_DAYS}天预警线",
            })

        # 生成补货建议（低于再订购点时）
        if item.current_stock <= item.reorder_point:
            # 订购量 = 双周需求量（经济批量简化）
            min_order = math.ceil(item.daily_demand * 14)
            arrival_date = str(date.today() + timedelta(days=item.lead_time_days))
            orders.append(ReplenishmentOrder(
                sku=item.sku,
                order_qty=min_order,
                urgency="critical" if item.status == "critical" else "standard",
                estimated_cost=min_order * item.unit_cost,
                earliest_arrival=arrival_date,
            ))

    return {
        "summary": {
            "total_skus": len(items),
            "critical_count": sum(1 for i in items if i.status == "critical"),
            "low_count": sum(1 for i in items if i.status == "low"),
            "total_inventory_value": round(total_value, 2),
        },
        "alerts": alerts,
        "replenishment_orders": [o.to_dict() for o in orders],
    }


def forecast_demand(history: list[float], forecast_days: int = 7) -> dict:
    """
    简单移动平均需求预测。

    Args:
        history: 历史每日需求列表（最近N天，新→旧）
        forecast_days: 预测未来天数

    Returns:
        dict: 预测结果
    """
    if len(history) < 3:
        avg = sum(history) / len(history) if history else 0
        return {"daily_avg": round(avg, 2), "forecast": [round(avg, 2)] * forecast_days,
                "trend": "stable", "confidence": "low"}

    # 加权移动平均（最近权重更高）
    n = min(len(history), 14)
    recent = history[:n]
    weights = list(range(1, n + 1))
    wma = sum(r * w for r, w in zip(recent, weights)) / sum(weights)

    # 趋势判断（前半 vs 后半）
    mid = n // 2
    first_half = sum(recent[mid:]) / max(mid, 1)
    second_half = sum(recent[:mid]) / max(mid, 1)
    if second_half > first_half * 1.1:
        trend = "increasing"
    elif second_half < first_half * 0.9:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "daily_avg": round(wma, 2),
        "forecast": [round(wma, 2)] * forecast_days,
        "trend": trend,
        "confidence": "medium" if n >= 7 else "low",
    }
