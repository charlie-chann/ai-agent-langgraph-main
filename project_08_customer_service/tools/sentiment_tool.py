# tools/sentiment_tool.py — 情感分析工具（基于规则的轻量判断，无需LLM调用）
"""
用户情感状态分析工具：检测负面情绪并判断是否需要升级。
生产环境可替换为LLM驱动的情感分析。
"""
from __future__ import annotations

import json
from langchain_core.tools import tool
from loguru import logger

from config import ESCALATION_SENTIMENT_THRESHOLD

# ── 情感词典（中文） ──────────────────────────────────────────────────────────
# 负面情感关键词及权重
_NEGATIVE_KEYWORDS: dict[str, float] = {
    # 愤怒类
    "愤怒": 0.9, "气死": 0.95, "骗子": 1.0, "欺骗": 0.9, "诈骗": 1.0,
    "投诉": 0.7, "举报": 0.85, "起诉": 0.95, "维权": 0.85,
    # 失望类
    "太差了": 0.7, "极差": 0.8, "垃圾": 0.8, "烂": 0.65,
    "失望": 0.6, "糟糕": 0.65, "差劲": 0.7, "不满意": 0.55,
    # 焦急类
    "紧急": 0.5, "急": 0.4, "马上": 0.3, "立刻": 0.3, "催": 0.45,
    # 威胁类
    "曝光": 0.9, "媒体": 0.8, "微博": 0.75, "黑猫": 0.8, "315": 0.85,
    "律师": 0.85, "法院": 0.9,
    # 负面用语
    "还没": 0.4, "一直": 0.35, "多次": 0.5, "再不": 0.6, "无法接受": 0.75,
    "要求退款": 0.65, "要求退货": 0.6, "问题没解决": 0.7, "没有人": 0.5,
}

# 正面情感关键词
_POSITIVE_KEYWORDS: list[str] = [
    "谢谢", "感谢", "满意", "好的", "非常好", "完美", "赞", "棒",
    "理解", "好用", "顺利", "解决了", "已收到", "辛苦了", "好评",
]


def _analyse_text(text: str) -> dict:
    """对文本进行情感打分（内部函数）。"""
    text_lower = text.lower()
    neg_score = 0.0
    triggered_kws = []

    for kw, weight in _NEGATIVE_KEYWORDS.items():
        if kw in text:
            neg_score = min(1.0, neg_score + weight)
            triggered_kws.append(kw)

    pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text)
    # 正面词汇降低负面得分
    neg_score = max(0.0, neg_score - pos_count * 0.1)

    # 长文本积累一定负面分
    if len(text) > 200 and neg_score > 0.3:
        neg_score = min(1.0, neg_score + 0.1)

    # 判断情感类别
    if neg_score >= 0.7:
        sentiment = "negative"
        emotions = ["愤怒/强烈不满"]
    elif neg_score >= 0.4:
        sentiment = "negative"
        emotions = ["失望/不满"]
    elif neg_score >= 0.2:
        sentiment = "neutral"
        emotions = ["轻微不满"]
    elif pos_count > 0:
        sentiment = "positive"
        emotions = ["满意/正向"]
    else:
        sentiment = "neutral"
        emotions = ["中性"]

    needs_escalation = neg_score >= ESCALATION_SENTIMENT_THRESHOLD

    if needs_escalation:
        suggested_tone = "共情安抚，主动提出升级人工服务"
    elif neg_score >= 0.4:
        suggested_tone = "共情回应，耐心解决问题"
    else:
        suggested_tone = "正常专业"

    return {
        "sentiment": sentiment,
        "score": round(neg_score, 3),
        "emotions": emotions,
        "triggered_keywords": triggered_kws[:5],
        "needs_escalation": needs_escalation,
        "suggested_tone": suggested_tone,
    }


@tool
def analyse_sentiment(message: str) -> str:
    """分析用户消息的情感状态。
    输入：用户消息文本
    输出：JSON格式情感分析结果，包含情感类别、负面程度评分（0-1）、
         是否需要升级、建议回复语气。
    """
    if not message.strip():
        return json.dumps({"sentiment": "neutral", "score": 0.0, "needs_escalation": False}, ensure_ascii=False)

    result = _analyse_text(message)
    logger.info(f"[sentiment] score={result['score']} needs_escalation={result['needs_escalation']}")
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def classify_intent(message: str) -> str:
    """识别用户消息的服务意图。
    输入：用户消息文本
    输出：JSON，包含意图标签和置信度。
    意图类别：query_faq/order_status/complaint/refund/
              technical_support/account_issue/billing/general
    """
    message_lower = message.lower()
    scores: dict[str, float] = {}

    # 规则匹配意图
    _INTENT_RULES: dict[str, list[str]] = {
        "order_status": ["订单", "物流", "快递", "发货", "配送", "几天", "到了吗", "到货", "收到"],
        "refund": ["退款", "退钱", "退货", "退换", "换货", "申请退"],
        "complaint": ["投诉", "不满意", "差评", "骗", "骗子", "欺诈", "问题很严重", "要求赔偿"],
        "account_issue": ["账户", "登录", "密码", "注册", "注销", "无法登录", "账号", "手机号"],
        "billing": ["账单", "扣款", "发票", "收费", "多扣", "费用", "充值", "余额"],
        "technical_support": ["故障", "闪退", "崩溃", "无法使用", "打不开", "报错", "bug", "卡顿"],
        "query_faq": ["怎么", "如何", "是什么", "有没有", "支持", "功能", "使用方法"],
    }

    for intent, keywords in _INTENT_RULES.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        if score > 0:
            scores[intent] = score

    if scores:
        top_intent = max(scores, key=lambda k: scores[k])
        confidence = min(1.0, scores[top_intent] / 3)
    else:
        top_intent = "general"
        confidence = 0.5

    return json.dumps({
        "intent": top_intent,
        "confidence": round(confidence, 2),
        "all_scores": scores,
    }, ensure_ascii=False, indent=2)
