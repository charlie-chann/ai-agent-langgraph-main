"""app.py — 客服全链路 Agent Streamlit UI（项目08）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import streamlit as st
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, COMPANY_NAME

st.set_page_config(
    page_title=f"🎧 {COMPANY_NAME}客服",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 侧边栏 ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## 🎧 {COMPANY_NAME}")
    st.caption("AI 客服全链路系统 — 智能问答 · 工单管理 · 情感感知")
    st.divider()

    model = st.selectbox("LLM 模型", [DEFAULT_MODEL, "qwen3.5:7b"], index=0)
    st.caption(f"Ollama: `{OLLAMA_BASE_URL}`")
    st.divider()

    mode = st.radio(
        "功能模式",
        ["💬 智能客服", "📦 订单查询", "🎫 工单管理", "📚 知识库"],
        index=0,
    )
    st.divider()

    # 用户身份模拟
    st.markdown("**模拟用户**")
    user_id = st.selectbox(
        "选择用户",
        ["u001 (张小明)", "u002 (李华)", "u003 (王芳)", "anonymous (匿名)"],
        index=0,
    )
    user_id = user_id.split(" ")[0]

    if st.button("🗑 清除对话记录"):
        st.session_state.messages = []
        from agent import clear_session
        clear_session(user_id)
        st.rerun()

# ── 订单查询模式 ───────────────────────────────────────────────────────────────
if mode == "📦 订单查询":
    st.subheader("📦 订单查询")
    col1, col2 = st.columns([2, 1])
    with col1:
        order_id = st.text_input("订单编号", placeholder="ORD2024001")
    with col2:
        st.write("")
        st.write("")
        query_btn = st.button("🔍 查询")

    if query_btn and order_id.strip():
        from tools.order_tool import query_order_status
        result = query_order_status.invoke(order_id.strip())
        try:
            data = json.loads(result)
            if data.get("found"):
                o = data
                st.success(f"✅ 找到订单 **{o['order_id']}**")
                cols = st.columns(4)
                cols[0].metric("商品", o["product"][:10] + "…")
                cols[1].metric("金额", o["amount"])
                cols[2].metric("状态", o["status"])
                cols[3].metric("快递", o["tracking"]["carrier"])

                st.markdown("**物流轨迹**")
                for event in reversed(o["full_logistics"]):
                    st.write(f"🕐 `{event['time']}` — {event['event']}")
            else:
                st.warning(data.get("message", "未找到订单"))
        except Exception:
            st.code(result)

    st.divider()
    st.subheader(f"用户 {user_id} 的所有订单")
    if st.button("📋 查看我的订单"):
        from tools.order_tool import list_user_orders
        result = list_user_orders.invoke(user_id)
        try:
            data = json.loads(result)
            if data.get("total_orders", 0) > 0:
                for o in data["orders"]:
                    st.write(f"**{o['order_id']}** — {o['product']} | {o['amount']} | _{o['status']}_ | {o['created_at']}")
            else:
                st.info("该用户暂无订单记录")
        except Exception:
            st.code(result)

# ── 工单管理模式 ───────────────────────────────────────────────────────────────
elif mode == "🎫 工单管理":
    st.subheader("🎫 工单管理")
    tab1, tab2, tab3 = st.tabs(["创建工单", "查询工单", "我的工单"])

    with tab1:
        title = st.text_input("工单标题", placeholder="简短描述您的问题")
        desc = st.text_area("问题描述", height=120, placeholder="请详细描述遇到的问题……")
        intent = st.selectbox("问题类型", [
            "general", "complaint", "refund", "technical_support",
            "order_status", "billing", "account_issue",
        ])
        if st.button("📤 提交工单") and title and desc:
            from tools.ticket_tool import create_ticket
            result = create_ticket.invoke({
                "user_id": user_id, "title": title,
                "description": desc, "intent": intent,
            })
            data = json.loads(result)
            if data.get("success"):
                st.success(data["message"])
                t = data["ticket"]
                st.json({"工单ID": t["ticket_id"], "优先级": t["priority"], "SLA截止": t["sla_deadline"]})
            else:
                st.error(result)

    with tab2:
        tid = st.text_input("工单编号", placeholder="TK01000")
        if st.button("🔍 查询") and tid:
            from tools.ticket_tool import get_ticket
            result = get_ticket.invoke(tid.strip().upper())
            data = json.loads(result)
            if data.get("found"):
                t = data["ticket"]
                status_color = "🟢" if t["status"] == "resolved" else ("🔴" if t["status"] == "escalated" else "🟡")
                st.markdown(f"**{t['ticket_id']}** — {t['title']}")
                st.write(f"{status_color} 状态: **{t['status']}** | 优先级: **{t['priority']}** | 创建: {t['created_at']}")
                st.write(f"描述: {t['description']}")
                if t["comments"]:
                    st.markdown("**处理记录：**")
                    for c in t["comments"]:
                        st.info(f"🕐 {c['time']}: {c['content']}")
            else:
                st.warning("工单不存在")

    with tab3:
        if st.button("📋 查看我的工单"):
            from tools.ticket_tool import list_user_tickets
            result = list_user_tickets.invoke(user_id)
            data = json.loads(result)
            total = data.get("total", 0)
            st.write(f"共 {total} 个工单")
            for t in data.get("tickets", []):
                st.write(f"**{t['ticket_id']}** — {t['title']} | _{t['status']}_ | {t['priority']}")

# ── 知识库模式 ─────────────────────────────────────────────────────────────────
elif mode == "📚 知识库":
    st.subheader("📚 知识库检索")
    query = st.text_input("搜索关键词", placeholder="退款 / 密码 / 发票 / 物流……")
    if st.button("🔍 搜索") and query:
        from tools.kb_tool import search_kb
        result = search_kb.invoke(query)
        data = json.loads(result)
        if data.get("found"):
            for item in data["results"]:
                with st.expander(f"📄 [{item['category']}] {item['question']} (相关度: {item['relevance_score']})"):
                    st.markdown(item["answer"])
        else:
            st.info("未找到相关内容，建议提交工单由人工处理")

    st.divider()
    st.subheader("知识库分类概览")
    from tools.kb_tool import list_kb_categories
    cats = json.loads(list_kb_categories.invoke(None))
    st.metric("知识库总文章数", cats["total_articles"])
    for cat, cnt in cats["categories"].items():
        st.write(f"• **{cat}**: {cnt} 篇")

# ── 智能客服聊天模式 ───────────────────────────────────────────────────────────
else:
    st.subheader(f"💬 AI 智能客服 — 用户：{user_id}")
    st.caption("全程由 AI 驱动，自动识别意图、搜索知识库、创建工单、查询订单")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 示例问题
    examples = [
        "我的订单ORD2024002什么时候能到？",
        "怎么申请退款？",
        "APP一直闪退，帮我解决一下",
        "我要投诉！你们的产品质量太差了，我要求赔偿！",
        "密码忘记了怎么办",
        "支持哪些付款方式",
    ]
    with st.expander("💡 常见问题示例"):
        for ex in examples:
            if st.button(ex, key=ex):
                st.session_state._prefill = ex

    # 渲染历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # 显示情感分析结果（仅用户消息）
            if msg.get("sentiment"):
                sent = msg["sentiment"]
                score = sent.get("score", 0)
                if score >= 0.7:
                    st.error(f"🔴 检测到强烈不满情绪（评分 {score:.2f}），已触发升级提醒")
                elif score >= 0.4:
                    st.warning(f"🟡 负面情绪检测（评分 {score:.2f}）")
            if msg.get("steps"):
                with st.expander(f"🔧 {len(msg['steps'])} 次工具调用", expanded=False):
                    for step in msg["steps"]:
                        st.markdown(f"**`{step['tool']}`** ← `{step['input'][:80]}`")
                        st.code(step["output"][:400], language=None)

    prompt = st.chat_input("请输入您的问题……")
    if not prompt and st.session_state.get("_prefill"):
        prompt = st.session_state.pop("_prefill")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt, "sentiment": None})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            container = st.empty()
            steps_ph = st.empty()
            sentiment_ph = st.empty()

            try:
                from agent import run_agent
                result = run_agent(prompt, user_id=user_id, model=model)
                output = result["output"]
                sentiment = result["sentiment"]
                steps = result["steps"]

                container.markdown(output)

                # 情感警告
                score = sentiment.get("score", 0)
                if score >= 0.7:
                    sentiment_ph.error("🔴 检测到强烈不满情绪，建议优先处理并考虑升级到人工客服")
                elif score >= 0.4:
                    sentiment_ph.warning(f"🟡 用户情绪偏负面（{sentiment.get('emotions', [''])[0]}），请注意回复方式")

                if steps:
                    with steps_ph.expander(f"🔧 {len(steps)} 次工具调用", expanded=False):
                        for s in steps:
                            st.markdown(f"**`{s['tool']}`**")
                            st.code(f"输入: {s['input']}\n输出: {s['output']}", language=None)

                # 更新消息记录（加入情感数据）
                st.session_state.messages[-1]["sentiment"] = sentiment
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": output,
                    "steps": steps,
                })

            except Exception as e:
                err = f"❌ 系统错误: {e}"
                container.error(err)
                logger.error(f"[app] {e}")
                st.session_state.messages.append({"role": "assistant", "content": err})
