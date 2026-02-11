"""Project 30 - 营销活动规划 Agent Streamlit UI"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agent import (
    run_plan_campaign, run_get_platform_schedule, run_get_phase_tasks,
    run_estimate_reach, run_list_campaign_types, stream_chat
)
from config import TARGET_PLATFORMS

st.set_page_config(
    page_title="📣 营销活动规划 Agent",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.markdown("# 📣 营销活动规划 Agent")
    st.caption("OpenClaw 核心能力 · Project 30")
    st.divider()
    st.markdown("**功能**")
    st.markdown("- 📋 生成完整营销日历\n- 📅 按平台查看发布计划\n- 📈 触达量预估\n- 💬 AI助手解答")
    st.divider()
    st.caption("OpenClaw · Ollama qwen3.5")

CAMPAIGN_TYPE_LABELS = {
    "product_launch": "🚀 产品发布",
    "brand_awareness": "🌟 品牌曝光",
    "seasonal": "🎉 节日营销",
    "engagement": "💬 用户互动",
    "lead_generation": "🎯 潜在客户"
}

PHASE_EMOJI = {"预热": "🔥", "爆发": "💥", "持续": "📈", "收尾": "🏁"}

tab1, tab2, tab3, tab4 = st.tabs(["📋 规划活动", "📅 平台日程", "📈 触达预估", "💬 AI 助手"])

with tab1:
    st.header("📋 生成营销活动计划")
    st.caption("一键生成完整的跨平台内容日历")

    with st.form("campaign_form"):
        campaign_name = st.text_input("活动名称", placeholder="618 大促活动")
        campaign_type = st.selectbox(
            "活动类型",
            run_list_campaign_types(),
            format_func=lambda x: CAMPAIGN_TYPE_LABELS.get(x, x)
        )
        col1, col2 = st.columns(2)
        with col1:
            duration_days = st.slider("活动周期（天）", 3, 90, 30)
            budget = st.number_input("预算（元）", value=10000.0, step=1000.0, min_value=0.0)
        with col2:
            platforms = st.multiselect(
                "目标平台",
                TARGET_PLATFORMS,
                default=TARGET_PLATFORMS[:3]
            )
            topic = st.text_input("核心话题/关键词", placeholder="国货品牌，618，促销")

        submitted = st.form_submit_button("🚀 生成活动计划", type="primary")

    if submitted:
        if not campaign_name:
            st.warning("请输入活动名称")
        elif not platforms:
            st.warning("请选择至少一个目标平台")
        else:
            with st.spinner("生成中，请稍候…"):
                result = run_plan_campaign(
                    campaign_name=campaign_name,
                    campaign_type=campaign_type,
                    duration_days=duration_days,
                    platforms=platforms,
                    budget=budget,
                    topic=topic
                )
            if result["success"]:
                plan = result["plan"]
                st.success(f"✅ 活动计划生成完毕！共 **{result['total_content']}** 个内容任务")
                col1, col2, col3 = st.columns(3)
                col1.metric("内容总量", result["total_content"])
                col2.metric("活动周期", f"{duration_days} 天")
                col3.metric("覆盖平台", len(platforms))

                with st.expander("📊 KPI 目标"):
                    for k, v in result["kpis"].items():
                        st.write(f"**{k}**: {v:,}")

                st.subheader("📅 完整活动日历（Markdown）")
                st.markdown(result["content"])

                st.session_state["last_plan"] = plan
            else:
                st.error(f"生成失败: {result.get('error')}")

with tab2:
    st.header("📅 平台内容日程")
    st.caption("查看特定平台的详细发布安排")

    if "last_plan" not in st.session_state:
        st.info("请先在【规划活动】标签页生成一个活动计划")
    else:
        plan = st.session_state["last_plan"]
        available_platforms = list({t.platform for t in plan.content_calendar})

        sel_platform = st.selectbox("选择平台", available_platforms)
        tasks = run_get_platform_schedule(plan, sel_platform)

        st.write(f"**{sel_platform}** 共 **{len(tasks)}** 个内容任务")

        for phase in ["预热", "爆发", "持续", "收尾"]:
            phase_tasks = [t for t in tasks if t.phase == phase]
            if phase_tasks:
                with st.expander(f"{PHASE_EMOJI.get(phase, '')} {phase} ({len(phase_tasks)} 个任务)"):
                    for t in phase_tasks:
                        col1, col2, col3 = st.columns([2, 2, 1])
                        col1.write(f"**{t.scheduled_date}**")
                        col2.write(t.content_type)
                        col3.write(t.title[:30])

with tab3:
    st.header("📈 触达量预估")
    st.caption("基于活动计划估算各平台、各阶段的内容触达总量")

    if "last_plan" not in st.session_state:
        st.info("请先在【规划活动】标签页生成一个活动计划")
    else:
        plan = st.session_state["last_plan"]
        reach = run_estimate_reach(plan)

        st.metric("🎯 预估总触达量", f"{reach['total_estimated_reach']:,}")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("按平台分布")
            for platform, cnt in sorted(reach["by_platform"].items(),
                                         key=lambda x: -x[1]):
                pct = cnt / reach["total_estimated_reach"] if reach["total_estimated_reach"] else 0
                st.progress(pct, text=f"{platform}: {cnt:,}")

        with col2:
            st.subheader("按阶段分布")
            for phase, cnt in sorted(reach["by_phase"].items(),
                                      key=lambda x: -x[1]):
                pct = cnt / reach["total_estimated_reach"] if reach["total_estimated_reach"] else 0
                st.progress(pct, text=f"{PHASE_EMOJI.get(phase, '')} {phase}: {cnt:,}")

with tab4:
    st.header("💬 AI 营销规划助手")
    st.caption("向 AI 提问关于营销策略、内容创作、平台选择的问题")

    if "messages_30" not in st.session_state:
        st.session_state.messages_30 = []

    for msg in st.session_state.messages_30:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("例如：适合小红书的启动期内容有哪些？"):
        st.session_state.messages_30.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            container = st.empty()
            full = ""
            try:
                for chunk in stream_chat(prompt):
                    full += chunk
                    container.markdown(full + "▌")
                container.markdown(full)
            except Exception as e:
                container.error(str(e))
                full = str(e)
        st.session_state.messages_30.append({"role": "assistant", "content": full})
