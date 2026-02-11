# app.py — 供应链优化 Agent Streamlit UI
#
# 【功能】
#   Tab1 库存分析  → run_inventory_analysis()
#   Tab2 路径优化  → run_route_optimization()
#   Tab3 AI 助手   → stream_chat()
import json
import streamlit as st

st.set_page_config(
    page_title="🚚 Supply Chain Agent",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL
from agent import run_inventory_analysis, run_route_optimization, stream_chat

_DEMO_INVENTORY = [
    {"sku": "SKU001", "name": "矿泉水 500ml", "current_stock": 20, "daily_demand": 10, "unit_cost": 1.5, "lead_time_days": 2},
    {"sku": "SKU002", "name": "方便面", "current_stock": 200, "daily_demand": 15, "unit_cost": 3.0, "lead_time_days": 3},
    {"sku": "SKU003", "name": "纸巾", "current_stock": 50, "daily_demand": 8, "unit_cost": 2.5, "lead_time_days": 4},
]

_DEMO_DEPOT = {"id": "DEPOT", "name": "中心仓库", "lat": 31.23, "lon": 121.47}
_DEMO_STOPS = [
    {"id": "S1", "name": "浦东门店", "lat": 31.22, "lon": 121.55, "demand": 50},
    {"id": "S2", "name": "徐汇门店", "lat": 31.19, "lon": 121.43, "demand": 30},
    {"id": "S3", "name": "静安门店", "lat": 31.24, "lon": 121.45, "demand": 40},
    {"id": "S4", "name": "杨浦门店", "lat": 31.27, "lon": 121.52, "demand": 25},
]


with st.sidebar:
    st.markdown("## 🚚 Supply Chain Agent")
    st.caption("库存预警 · 补货建议 · TSP 路径 · AI 对话")
    st.divider()
    st.markdown(f"**模型:** `{DEFAULT_MODEL}`")
    st.caption(f"Ollama: `{OLLAMA_BASE_URL}`")
    st.divider()
    st.info("算法 Tab 无需 LLM；AI 助手 Tab 需要 Ollama 在线。")

st.title("🚚 供应链优化 Agent")
st.caption("库存健康度 · 移动平均预测 · TSP 路径优化 · LLM 供应链助手")

tab1, tab2, tab3 = st.tabs(["📦 库存分析", "🗺️ 路径优化", "💬 AI 助手"])

with tab1:
    st.markdown("输入 SKU 库存数据（JSON 数组），或使用演示数据。")
    inv_text = st.text_area(
        "库存 JSON",
        value=json.dumps(_DEMO_INVENTORY, ensure_ascii=False, indent=2),
        height=200,
    )
    if st.button("📦 运行库存分析", type="primary", key="inv_btn"):
        try:
            items_data = json.loads(inv_text)
            if not isinstance(items_data, list):
                raise ValueError("库存数据必须是 JSON 数组")
            with st.spinner("分析库存..."):
                result = run_inventory_analysis(items_data)
            summary = result["summary"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("SKU 总数", summary["total_skus"])
            c2.metric("紧急缺货", summary["critical_count"])
            c3.metric("低库存", summary["low_count"])
            c4.metric("库存总值", f"¥{summary['total_inventory_value']:,.2f}")
            if result["alerts"]:
                st.warning("库存预警")
                for alert in result["alerts"]:
                    st.markdown(f"- **{alert['sku']}** ({alert['name']}): {alert['message']}")
            if result["replenishment_orders"]:
                st.markdown("**补货建议**")
                st.dataframe(result["replenishment_orders"], use_container_width=True)
            with st.expander("完整分析结果"):
                st.json(result)
        except Exception as e:
            st.error(f"分析失败: {e}")

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        depot_text = st.text_area("仓库 JSON", value=json.dumps(_DEMO_DEPOT, ensure_ascii=False, indent=2), height=120)
    with col2:
        stops_text = st.text_area("配送站点 JSON", value=json.dumps(_DEMO_STOPS, ensure_ascii=False, indent=2), height=120)
    if st.button("🗺️ 优化配送路径", type="primary", key="route_btn"):
        try:
            depot_data = json.loads(depot_text)
            stops_data = json.loads(stops_text)
            with st.spinner("计算最优路径..."):
                result = run_route_optimization(depot_data, stops_data)
            c1, c2, c3 = st.columns(3)
            c1.metric("总距离", f"{result.get('总距离(km)', 0)} km")
            c2.metric("预计耗时", f"{result.get('预计耗时(h)', 0)} h")
            c3.metric("站点数", result.get("站点数", 0))
            st.markdown(f"**配送顺序:** {' → '.join(result.get('配送顺序', []))}")
            risks = result.get("delay_risks", [])
            if risks:
                st.warning("延误风险")
                for r in risks:
                    st.markdown(f"- {r['stop_name']}: {r['risk']}（预计 {r['estimated_arrival']}）")
            else:
                st.success("未检测到时间窗口延误风险")
            with st.expander("完整路径结果"):
                st.json(result)
        except Exception as e:
            st.error(f"优化失败: {e}")

with tab3:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("问供应链问题，例如：如何降低缺货率？")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            response = st.write_stream(
                stream_chat(prompt, st.session_state.chat_history[:-1])
            )
        st.session_state.chat_history.append({"role": "assistant", "content": response})
