"""tests/test_agent.py — project_08_customer_service 单元测试"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
import pytest


def _load(module_name: str, rel_path: str):
    """按文件路径加载模块，避免全局 agent 包冲突。"""
    path = Path(__file__).parent.parent / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 知识库工具测试 ─────────────────────────────────────────────────────────────
class TestKBTool:
    def setup_method(self):
        self.mod = _load("kb_tool", "tools/kb_tool.py")

    def test_search_finds_relevant_article(self):
        """搜索'密码'应返回相关FAQ"""
        result = self.mod.search_kb.invoke("密码忘记了怎么重置")
        data = json.loads(result)
        assert data["found"] is True
        titles = [r["question"] for r in data["results"]]
        assert any("密码" in t for t in titles)

    def test_search_returns_max_results(self):
        """搜索结果不超过 MAX_KB_RESULTS"""
        result = self.mod.search_kb.invoke("账户安全登录")
        data = json.loads(result)
        if data["found"]:
            assert len(data["results"]) <= 3

    def test_search_no_match_returns_not_found(self):
        """无关查询应返回 found=False"""
        result = self.mod.search_kb.invoke("xyzabc12345不存在的内容")
        data = json.loads(result)
        assert data["found"] is False

    def test_list_categories_returns_dict(self):
        """分类列表应包含正确字段"""
        result = self.mod.list_kb_categories.invoke(None)
        data = json.loads(result)
        assert "total_articles" in data
        assert data["total_articles"] > 0
        assert "categories" in data

    def test_search_refund_topic(self):
        """退款相关查询应命中退款FAQ"""
        result = self.mod.search_kb.invoke("我要申请退款")
        data = json.loads(result)
        assert data["found"] is True


# ── 情感分析工具测试 ───────────────────────────────────────────────────────────
class TestSentimentTool:
    def setup_method(self):
        self.mod = _load("sentiment_tool", "tools/sentiment_tool.py")

    def test_angry_message_high_score(self):
        """强烈投诉应返回高负面分数"""
        result = self.mod.analyse_sentiment.invoke("你们是骗子！我要投诉到315！")
        data = json.loads(result)
        assert data["score"] >= 0.7
        assert data["needs_escalation"] is True

    def test_neutral_message_low_score(self):
        """中性消息应返回低负面分数"""
        result = self.mod.analyse_sentiment.invoke("请问你们支持哪些付款方式？")
        data = json.loads(result)
        assert data["score"] < 0.4
        assert data["needs_escalation"] is False

    def test_positive_message(self):
        """正面消息应有较低负面分"""
        result = self.mod.analyse_sentiment.invoke("非常感谢！问题解决了，好评！")
        data = json.loads(result)
        assert data["score"] < 0.3

    def test_empty_message(self):
        """空消息不应崩溃"""
        result = self.mod.analyse_sentiment.invoke("")
        data = json.loads(result)
        assert "sentiment" in data

    def test_classify_order_intent(self):
        """订单查询意图识别"""
        result = self.mod.classify_intent.invoke("我的订单什么时候发货？")
        data = json.loads(result)
        assert data["intent"] == "order_status"

    def test_classify_refund_intent(self):
        """退款意图识别"""
        result = self.mod.classify_intent.invoke("我要申请退货退款")
        data = json.loads(result)
        assert data["intent"] == "refund"

    def test_classify_complaint_intent(self):
        """投诉意图识别"""
        result = self.mod.classify_intent.invoke("我要投诉，产品质量太差了")
        data = json.loads(result)
        assert data["intent"] == "complaint"


# ── 工单工具测试 ───────────────────────────────────────────────────────────────
class TestTicketTool:
    def setup_method(self):
        self.mod = _load("ticket_tool", "tools/ticket_tool.py")
        # 每次测试重置内存存储
        self.mod._TICKETS.clear()
        self.mod._TICKET_COUNTER["n"] = 1000

    def test_create_ticket_success(self):
        """创建工单应返回工单ID"""
        result = self.mod.create_ticket.invoke({
            "user_id": "u001",
            "title": "APP无法登录",
            "description": "点击登录按钮后没有反应",
            "intent": "technical_support",
        })
        data = json.loads(result)
        assert data["success"] is True
        assert "TK" in data["ticket_id"]
        assert data["ticket"]["priority"] == "P3"  # technical_support → P3

    def test_create_ticket_complaint_has_p2_priority(self):
        """投诉类工单应自动设为P2优先级"""
        result = self.mod.create_ticket.invoke({
            "user_id": "u002",
            "title": "产品质量投诉",
            "description": "收到的商品有破损",
            "intent": "complaint",
        })
        data = json.loads(result)
        assert data["ticket"]["priority"] == "P2"

    def test_create_ticket_empty_fields_error(self):
        """缺少必要字段应返回错误"""
        result = self.mod.create_ticket.invoke({
            "user_id": "",
            "title": "",
            "description": "test",
        })
        assert "错误" in result or "Error" in result

    def test_get_ticket_found(self):
        """创建后可查询工单"""
        create_raw = self.mod.create_ticket.invoke({
            "user_id": "u001", "title": "测试", "description": "测试描述",
        })
        tid = json.loads(create_raw)["ticket_id"]
        result = self.mod.get_ticket.invoke(tid)
        data = json.loads(result)
        assert data["found"] is True
        assert data["ticket"]["ticket_id"] == tid

    def test_get_nonexistent_ticket(self):
        """查询不存在的工单应返回 found=False"""
        result = self.mod.get_ticket.invoke("TK99999")
        data = json.loads(result)
        assert data["found"] is False

    def test_update_ticket_status(self):
        """工单状态更新"""
        create_raw = self.mod.create_ticket.invoke({
            "user_id": "u001", "title": "测试状态更新", "description": "描述",
        })
        tid = json.loads(create_raw)["ticket_id"]
        result = self.mod.update_ticket_status.invoke({
            "ticket_id": tid, "status": "in_progress", "comment": "正在处理中",
        })
        data = json.loads(result)
        assert data["success"] is True
        assert data["new_status"] == "in_progress"

    def test_escalate_ticket(self):
        """工单升级应修改优先级为P1"""
        create_raw = self.mod.create_ticket.invoke({
            "user_id": "u003", "title": "紧急问题", "description": "资金问题",
        })
        tid = json.loads(create_raw)["ticket_id"]
        result = self.mod.escalate_ticket.invoke({
            "ticket_id": tid, "reason": "客户情绪激动，要求人工处理",
        })
        data = json.loads(result)
        assert data["success"] is True
        # 确认工单状态已升级
        ticket = self.mod._TICKETS[tid]
        assert ticket["status"] == "escalated"
        assert ticket["priority"] == "P1"


# ── 订单工具测试 ───────────────────────────────────────────────────────────────
class TestOrderTool:
    def setup_method(self):
        self.mod = _load("order_tool", "tools/order_tool.py")

    def test_query_existing_order(self):
        """查询存在的订单"""
        result = self.mod.query_order_status.invoke("ORD2024001")
        data = json.loads(result)
        assert data["found"] is True
        assert data["order_id"] == "ORD2024001"
        assert "status" in data
        assert len(data["full_logistics"]) > 0

    def test_query_nonexistent_order(self):
        """查询不存在的订单"""
        result = self.mod.query_order_status.invoke("ORD9999999")
        data = json.loads(result)
        assert data["found"] is False

    def test_list_user_orders_found(self):
        """查询存在订单的用户"""
        result = self.mod.list_user_orders.invoke("u001")
        data = json.loads(result)
        assert data.get("total_orders", 0) > 0

    def test_list_user_orders_not_found(self):
        """查询无订单的用户"""
        result = self.mod.list_user_orders.invoke("unknown_user_xyz")
        data = json.loads(result)
        assert data.get("found") is False or data.get("total_orders", 0) == 0
