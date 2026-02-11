# tools/order_tool.py — 模拟订单状态查询工具
"""
生产环境应替换为真实的订单数据库或ERP接口调用。
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone, timedelta
from langchain_core.tools import tool
from loguru import logger

# ── 模拟订单数据库 ─────────────────────────────────────────────────────────────
def _gen_date(days_ago: int) -> str:
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%d %H:%M")


_MOCK_ORDERS: dict[str, dict] = {
    "ORD2024001": {
        "order_id": "ORD2024001", "user_id": "u001",
        "product": "智能手表 Pro X1", "quantity": 1, "amount": 1299.00,
        "status": "delivered", "payment_status": "paid",
        "created_at": _gen_date(10),
        "tracking_number": "SF1234567890",
        "carrier": "顺丰速运",
        "logistics": [
            {"time": _gen_date(10), "event": "商家已接单，备货中"},
            {"time": _gen_date(9), "event": "订单已揽收，运往转运中心"},
            {"time": _gen_date(8), "event": "已到达北京转运中心"},
            {"time": _gen_date(7), "event": "派件中，预计今日送达"},
            {"time": _gen_date(7), "event": "✅ 已签收，签收人：本人"},
        ],
    },
    "ORD2024002": {
        "order_id": "ORD2024002", "user_id": "u001",
        "product": "无线蓝牙耳机 S9", "quantity": 2, "amount": 598.00,
        "status": "shipped", "payment_status": "paid",
        "created_at": _gen_date(3),
        "tracking_number": "ZTO9876543210",
        "carrier": "中通快递",
        "logistics": [
            {"time": _gen_date(3), "event": "商家已打包，等待快递揽收"},
            {"time": _gen_date(2), "event": "快递已揽收"},
            {"time": _gen_date(1), "event": "已到达上海转运中心"},
            {"time": _gen_date(0), "event": "已转至目的地城市，正在派送"},
        ],
    },
    "ORD2024003": {
        "order_id": "ORD2024003", "user_id": "u002",
        "product": "机械键盘 RGB版", "quantity": 1, "amount": 459.00,
        "status": "processing", "payment_status": "paid",
        "created_at": _gen_date(1),
        "tracking_number": None,
        "carrier": None,
        "logistics": [
            {"time": _gen_date(1), "event": "订单已支付，商家处理中"},
        ],
    },
    "ORD2024004": {
        "order_id": "ORD2024004", "user_id": "u003",
        "product": "显示器 27寸 4K", "quantity": 1, "amount": 2399.00,
        "status": "refund_processing", "payment_status": "refund_requested",
        "created_at": _gen_date(15),
        "tracking_number": "YTO1122334455",
        "carrier": "圆通速递",
        "logistics": [
            {"time": _gen_date(15), "event": "订单已支付"},
            {"time": _gen_date(14), "event": "已发货"},
            {"time": _gen_date(12), "event": "已签收"},
            {"time": _gen_date(5), "event": "用户申请退款，原因：屏幕存在亮点"},
            {"time": _gen_date(4), "event": "⏳ 退款审核中（预计1-3个工作日）"},
        ],
    },
}

_STATUS_CN = {
    "pending": "待支付", "paid": "已支付",
    "processing": "处理中", "shipped": "已发货",
    "delivered": "已签收", "cancelled": "已取消",
    "refund_requested": "退款申请中", "refund_processing": "退款处理中",
    "refunded": "已退款",
}


@tool
def query_order_status(order_id: str) -> str:
    """查询订单状态和物流信息。
    输入：订单编号（如 ORD2024001）
    返回：订单状态、物流轨迹、预计送达时间等信息。
    """
    order_id = order_id.strip().upper()
    order = _MOCK_ORDERS.get(order_id)
    if not order:
        return json.dumps({
            "found": False,
            "message": f"未找到订单 {order_id}，请确认订单号是否正确",
        }, ensure_ascii=False)

    status_cn = _STATUS_CN.get(order["status"], order["status"])
    result = {
        "found": True,
        "order_id": order["order_id"],
        "product": order["product"],
        "quantity": order["quantity"],
        "amount": f"¥{order['amount']:.2f}",
        "status": status_cn,
        "payment_status": _STATUS_CN.get(order["payment_status"], order["payment_status"]),
        "created_at": order["created_at"],
        "tracking": {
            "number": order["tracking_number"] or "待分配",
            "carrier": order["carrier"] or "待分配",
        },
        "latest_event": order["logistics"][-1]["event"] if order["logistics"] else "暂无物流信息",
        "full_logistics": order["logistics"],
    }
    logger.info(f"[order] query {order_id} status={order['status']}")
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def list_user_orders(user_id: str) -> str:
    """查询用户的所有订单列表。
    输入：用户ID
    返回：该用户的订单摘要列表。
    """
    user_id = user_id.strip()
    orders = [o for o in _MOCK_ORDERS.values() if o["user_id"] == user_id]
    if not orders:
        return json.dumps({
            "found": False,
            "message": f"用户 {user_id} 暂无订单记录"
        }, ensure_ascii=False)

    summary = [
        {
            "order_id": o["order_id"],
            "product": o["product"],
            "amount": f"¥{o['amount']:.2f}",
            "status": _STATUS_CN.get(o["status"], o["status"]),
            "created_at": o["created_at"],
        }
        for o in orders
    ]
    return json.dumps({
        "user_id": user_id,
        "total_orders": len(summary),
        "orders": summary,
    }, ensure_ascii=False, indent=2)
