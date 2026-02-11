"""
🧠 Self-Evolving RAG System
自进化RAG系统 - Streamlit 界面
"""

import streamlit as st
import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from rag_engine import SelfEvolvingRAG
    ENGINE_AVAILABLE = True
except Exception as e:
    ENGINE_AVAILABLE = False
    ENGINE_ERROR = str(e)

# ============ 页面配置 ============
st.set_page_config(
    page_title="Self-Evolving RAG",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ 自定义 CSS ============
st.markdown("""
<style>
    /* 全局字体 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* 隐藏默认的 Streamlit 元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 侧边栏 */
    .css-1d391kg {
        background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
    }

    /* 卡片样式 */
    .card {
        background: linear-gradient(135deg, #1e1e3f 0%, #252550 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 16px;
        padding: 20px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }

    .card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 8px 32px rgba(99, 102, 241, 0.15);
    }

    /* 状态指示器 */
    .status-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-green { background: #10b981; box-shadow: 0 0 8px #10b981; }
    .status-red { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
    .status-yellow { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }

    /* 统计数字 */
    .stat-number {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* 消息气泡 */
    .user-msg {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        color: white;
        border-radius: 20px 20px 4px 20px;
        padding: 16px 20px;
        margin: 8px 0;
        max-width: 85%;
        margin-left: auto;
    }

    .bot-msg {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: #e2e8f0;
        border-radius: 20px 20px 20px 4px;
        padding: 16px 20px;
        margin: 8px 0;
        border: 1px solid rgba(99, 102, 241, 0.2);
    }

    /* 来源标签 */
    .source-tag {
        display: inline-block;
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        margin: 4px 4px 4px 0;
    }

    /* 进度条 */
    .evo-progress {
        background: rgba(99, 102, 241, 0.1);
        border-radius: 8px;
        height: 8px;
        overflow: hidden;
    }
    .evo-progress-bar {
        background: linear-gradient(90deg, #6366f1, #a855f7);
        height: 100%;
        border-radius: 8px;
        transition: width 0.5s ease;
    }

    /* 侧边栏样式 */
    .sidebar-section {
        background: rgba(99, 102, 241, 0.1);
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
    }

    /* 标签 */
    .tag-blue { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
    .tag-green { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
    .tag-red { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
    .tag-yellow { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }

    /* 动画 */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .pulsing { animation: pulse 2s ease-in-out infinite; }

    /* 滚动条 */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.3); border-radius: 3px; }

    /* Chat container */
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding-right: 8px;
    }

    /* Metric cards */
    div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
</style>
""", unsafe_allow_html=True)


# ============ 初始化 RAG 引擎 ============
@st.cache_resource
def init_rag():
    """初始化RAG引擎（带缓存）"""
    try:
        rag = SelfEvolvingRAG()
        return rag, None
    except Exception as e:
        return None, str(e)


# ============ 侧边栏 ============
def render_sidebar(rag, status):
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("## 🧠 RAG 状态")

        # 系统状态卡片
        if status:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                <div class="card">
                    <div><span class="status-dot status-green"></span><strong>向量库</strong></div>
                    <div style="margin-top:8px">{} 文档块</div>
                </div>
                """.format(status.get("vector_store", {}).get("total_chunks", 0)), unsafe_allow_html=True)
            with col2:
                st.markdown("""
                <div class="card">
                    <div><span class="status-dot status-green"></span><strong>反馈数</strong></div>
                    <div style="margin-top:8px">{} 条</div>
                </div>
                """.format(status.get("feedback", {}).get("total", 0)), unsafe_allow_html=True)

        # 模型状态
        model_info = status.get("model", {})
        model_color = "status-green" if model_info.get("available") else "status-red"
        st.markdown(f"""
        <div class="card">
            <div><span class="status-dot {model_color}"></span><strong>Ollama 模型</strong></div>
            <div style="margin-top:8px;font-size:0.85rem">{model_info.get('model', 'N/A')}</div>
        </div>
        """, unsafe_allow_html=True)

        # 进化状态
        evo = status.get("evolution", {})
        st.markdown("---")
        st.markdown("### 🔄 进化引擎")

        if evo.get("evolution_events_total", 0) > 0:
            boosts = evo.get("recent_boosts", 0)
            penalties = evo.get("recent_penalties", 0)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div style="text-align:center">
                    <div style="color:#10b981;font-size:1.5rem">⬆ {boosts}</div>
                    <div style="font-size:0.75rem;color:#94a3b8">提升</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style="text-align:center">
                    <div style="color:#ef4444;font-size:1.5rem">⬇ {penalties}</div>
                    <div style="font-size:0.75rem;color:#94a3b8">降低</div>
                </div>
                """, unsafe_allow_html=True)

            # 进化进度
            total = boosts + penalties
            if total > 0:
                pct = boosts / total * 100
                st.markdown(f"""
                <div style="margin-top:12px">
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:4px">
                        <span>进化健康度</span><span>{pct:.0f}%</span>
                    </div>
                    <div class="evo-progress">
                        <div class="evo-progress-bar" style="width:{pct}%"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("尚未收集到反馈，系统尚未开始进化")

        # 知识库来源
        st.markdown("---")
        st.markdown("### 📚 知识库")
        if status.get("vector_store", {}).get("total_chunks", 0) > 0:
            st.success(f"已加载 {status['vector_store']['total_chunks']} 个文档块")
        else:
            st.warning("知识库为空，请上传文档")

        # 设置区域
        st.markdown("---")
        st.markdown("### ⚙️ 设置")

        use_evolution = st.toggle(
            "🧬 启用进化检索",
            value=True,
            help="启用后，系统会根据历史反馈优化检索结果"
        )

        top_k = st.slider(
            "📊 检索数量 (top_k)",
            min_value=1,
            max_value=20,
            value=5,
            help="每次检索返回的文档块数量"
        )

        return use_evolution, top_k


# ============ 主聊天界面 ============
def render_chat(rag, use_evolution, top_k):
    """渲染聊天界面"""
    st.markdown("""
    <div style="text-align:center;margin-bottom:32px">
        <h1 style="font-size:2.5rem;font-weight:700;margin-bottom:8px">
            🧠 <span style="background:linear-gradient(135deg,#6366f1,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent">自进化RAG</span>
        </h1>
        <p style="color:#94a3b8;font-size:1rem">基于 Ollama qwen3.5 + LangChain 构建 · 越用越聪明</p>
    </div>
    """, unsafe_allow_html=True)

    # 聊天容器
    chat_container = st.container()

    # 初始化会话历史
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "awaiting_feedback" not in st.session_state:
        st.session_state.awaiting_feedback = None

    # 显示历史消息
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="user-msg">{}</div>
                """.format(msg["content"]), unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="bot-msg">
                    <div style="margin-bottom:8px">{}</div>
                </div>
                """.format(msg["content"]), unsafe_allow_html=True)

                # 显示来源
                if msg.get("sources"):
                    st.markdown("<div style='margin-top:8px'>**📌 参考来源：**</div>", unsafe_allow_html=True)
                    for src in msg["sources"][:3]:
                        st.markdown(f"""
                        <span class="source-tag">{}</span>
                        """.format(src.get("source", "未知")), unsafe_allow_html=True)
                    st.markdown("---")

                # 显示反馈按钮状态
                if msg.get("feedback_submitted"):
                    st.markdown("""
                    <div style="color:#10b981;font-size:0.8rem;margin-top:8px">✅ 感谢您的反馈</div>
                    """, unsafe_allow_html=True)

    # 聊天输入
    st.markdown("---")
    col1, col2 = st.columns([5, 1])
    with col1:
        query = st.text_input(
            "💬 问我任何问题...",
            placeholder="输入问题，按 Enter 发送",
            label_visibility="collapsed",
            key="chat_input"
        )
    with col2:
        send_btn = st.button("发送 🚀", use_container_width=True)

    if query and send_btn:
        st.session_state.awaiting_feedback = None
        process_query(query, use_evolution, top_k)

    if query and not send_btn:
        if st.session_state.get("last_query") != query:
            st.session_state.last_query = query
            process_query(query, use_evolution, top_k)

    # 反馈处理
    if st.session_state.awaiting_feedback:
        render_feedback_form(st.session_state.awaiting_feedback)


def process_query(query, use_evolution, top_k):
    """处理用户查询"""
    # 添加用户消息
    st.session_state.messages.append({
        "role": "user",
        "content": query
    })

    with st.spinner("🧠 思考中..."):
        result = rag.ask(query, top_k=top_k, use_evolution=use_evolution)

        if result.get("ok"):
            answer = result["answer"]
        else:
            answer = f"抱歉，发生了错误：{result.get('error', 'Unknown error')}"

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": result.get("sources", []),
            "chunk_ids": result.get("chunk_ids", []),
            "feedback_submitted": False
        })

        # 标记等待反馈
        st.session_state.awaiting_feedback = {
            "question": query,
            "answer": answer,
            "chunk_ids": result.get("chunk_ids", []),
            "sources": result.get("sources", [])
        }

        st.rerun()


def render_feedback_form(pending):
    """渲染反馈表单"""
    st.markdown("---")
    st.markdown("### 📝 为这个回答打分")

    col1, col2, col3 = st.columns([1, 1, 2])

    rating = 0
    with col1:
        if st.button("👍 有帮助", use_container_width=True):
            rating = 1
    with col2:
        if st.button("👎 需改进", use_container_width=True):
            rating = -1

    if rating != 0:
        # 自动提交反馈
        score = 1.0 if rating == 1 else 0.0
        fb_result = rag.submit_feedback(
            question=pending["question"],
            answer=pending["answer"],
            chunk_ids=pending["chunk_ids"],
            rating=rating,
            score=score
        )

        # 标记反馈已提交
        for msg in reversed(st.session_state.messages):
            if msg.get("answer") == pending["answer"]:
                msg["feedback_submitted"] = True
                break

        st.session_state.awaiting_feedback = None
        st.success("✅ 感谢反馈！系统已学习并优化")
        st.rerun()

    with col3:
        correction = st.text_input(
            "✏️ 如果回答不满意，请提供修正内容（可选）",
            placeholder="这里填写你认为正确的答案...",
            label_visibility="collapsed"
        )
        if correction:
            fb_result = rag.submit_feedback(
                question=pending["question"],
                answer=pending["answer"],
                chunk_ids=pending["chunk_ids"],
                rating=-1,
                score=0.3,
                correction=correction
            )
            st.success("✅ 已记录修正内容")
            st.session_state.awaiting_feedback = None


# ============ 文档管理页面 ============
def render_knowledge_tab(rag):
    """渲染知识库管理页面"""
    st.markdown("## 📚 知识库管理")

    tab1, tab2, tab3 = st.tabs(["📤 上传文档", "📋 已上传列表", "🔍 知识分析"])

    with tab1:
        st.markdown("### 上传文件或文件夹")
        st.info("支持格式: .txt, .md, .pdf, .docx, .html, .json, .yaml, .csv")

        col1, col2 = st.columns(2)

        with col1:
            uploaded_file = st.file_uploader(
                "选择单个文件",
                type=["txt", "md", "pdf", "docx", "html", "json", "yaml", "csv"],
                help="上传文档到知识库"
            )
            if uploaded_file and st.button("⬆️ 解析上传", use_container_width=True):
                with st.spinner("解析中..."):
                    # 保存到临时文件
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as f:
                        f.write(uploaded_file.getvalue())
                        temp_path = f.name

                    result = rag.ingest_file(temp_path)
                    if result.get("ok"):
                        st.success(f"✅ 成功解析 {result['chunks']} 个文档块")
                    else:
                        st.error(f"❌ 失败: {result.get('error')}")

        with col2:
            folder_path = st.text_input(
                "或输入文件夹路径",
                placeholder="例如: C:/Users/charlie/Documents",
                help="批量导入文件夹下所有支持的文档"
            )
            if folder_path and st.button("📂 批量导入", use_container_width=True):
                with st.spinner("批量导入中..."):
                    result = rag.ingest_folder(folder_path)
                    if result.get("ok"):
                        st.success(f"✅ 成功导入 {result['chunks']} 个文档块")
                    else:
                        st.error(f"❌ 失败: {result.get('error')}")

        st.markdown("---")
        st.markdown("### ✏️ 直接输入文本")
        manual_text = st.text_area(
            "在此输入要加入知识库的文本",
            placeholder="输入你想要保存的知识内容...",
            height=150
        )
        if manual_text and st.button("💾 添加到知识库", use_container_width=True):
            result = rag.ingest_text(manual_text, source_name="manual_input")
            if result.get("ok"):
                st.success(f"✅ 已添加 {result['chunks']} 个文本块")
            else:
                st.error(f"❌ 失败: {result.get('error')}")

    with tab2:
        st.markdown("### 📋 知识库内容")
        status = rag.get_status()
        chunks = rag.vector_store.get_all_chunks(limit=50)

        if chunks:
            for chunk in chunks[:20]:
                with st.expander(f"📄 {chunk.get('source', 'Unknown')} (score: {chunk.get('score', 0):.2f})"):
                st.text(chunk["content"][:300] + "..." if len(chunk["content"]) > 300 else chunk["content"])
                st.caption(f"ID: {chunk['id']} | 命中: {chunk.get('hit_count', 0)} | 权重: {chunk.get('score', 0):.3f}")
        else:
            st.info("知识库为空，请先上传文档")

    with tab3:
        st.markdown("### 🔍 知识分析")
        evo_stats = rag.evolution.get_evolution_stats()
        gaps = rag.evolution.get_knowledge_gaps()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总反馈", evo_stats["feedback_stats"]["total"])
        with col2:
            st.metric("好评", evo_stats["feedback_stats"]["good"])
        with col3:
            st.metric("差评", evo_stats["feedback_stats"]["bad"])
        with col4:
            st.metric("进化事件", evo_stats["evolution_events_total"])

        if gaps:
            st.markdown("#### ⚠️ 知识盲点（差评高频话题）")
            for gap in gaps:
                st.markdown(f"- **{gap['keyword']}** (出现 {gap['frequency']} 次)")
        else:
            st.info("暂无差评数据")


# ============ 进化引擎页面 ============
def render_evolution_tab(rag):
    """渲染进化引擎页面"""
    st.markdown("## 🔄 自进化引擎")
    st.markdown("*系统根据您的反馈自动优化检索效果，越用越聪明*")

    col1, col2 = st.columns([2, 1])

    with col1:
        # 手动触发进化
        st.markdown("### 🎯 手动触发进化")
        st.markdown("分析所有反馈数据，批量更新文档块权重")

        if st.button("🚀 执行自进化", use_container_width=True, type="primary"):
            with st.spinner("🔄 执行进化中..."):
                result = rag.evolution.trigger_evolution()

            st.success(f"✅ 进化完成！更新了 {result['chunks_updated']} 个文档块")

            if result.get("top_chunks"):
                st.markdown("**⬆️ 表现最佳的文档块：**")
                for c in result["top_chunks"][:3]:
                    st.markdown(f"- {c['id']}: 净得分 {c['net']} (好:{c['good']} / 差:{c['bad']})")

            if result.get("bottom_chunks"):
                st.markdown("**⬇️ 表现最差的文档块：**")
                for c in result["bottom_chunks"][:3]:
                    st.markdown(f"- {c['id']}: 净得分 {c['net']} (好:{c['good']} / 差:{c['bad']})")

    with col2:
        st.markdown("### ⚙️ 进化参数")
        st.slider("好评阈值", 0.5, 0.9, 0.7, key="pos_thresh")
        st.slider("差评阈值", 0.1, 0.5, 0.3, key="neg_thresh")
        st.slider("权重调整幅度", 0.01, 0.3, 0.1, key="boost_weight")
        st.slider("触发频率（反馈数）", 5, 50, 10, key="auto_interval")

    st.markdown("---")
    st.markdown("### 📊 进化统计")

    status = rag.get_status()
    evo = status.get("evolution", {})

    # 时间线展示
    if evo.get("evolution_log"):
        st.markdown("#### 📜 近期进化事件")
        for event in evo["evolution_log"][-10:]:
            event_type = event.get("type", "")
            icon = "⬆️" if event_type == "boost" else "⬇️" if event_type in ("penalty", "penalize") else "📚" if event_type == "learn_correction" else "🔄"
            st.markdown(f"{icon} **{event_type}** - {event.get('timestamp', '')[:19]}")
    else:
        st.info("暂无进化记录，开始问答并提供反馈吧！")

    # 反馈历史
    st.markdown("---")
    st.markdown("### 📝 反馈历史")
    recent = rag.feedback.get_recent_feedback(limit=10)
    if recent:
        for fb in recent:
            rating_icon = "👍" if fb["rating"] == 1 else "👎"
            st.markdown(f"{rating_icon} **{fb['question'][:60]}**...")
            st.caption(f"评分: {fb['score']} | {fb['created_at'][:19]}")
    else:
        st.info("暂无反馈记录")


# ============ 主函数 ============
def main():
    """主函数"""
    # 初始化引擎
    rag, error = init_rag()

    if error:
        st.error(f"❌ 初始化失败: {error}")
        st.markdown("请确保：\n1. Ollama 服务正在运行 (`ollama serve`)\n2. 模型已下载 (`ollama pull qwen3.5:latest`)\n3. 依赖已安装 (`pip install -r requirements.txt`)")
        return

    status = rag.get_status()

    # 渲染侧边栏
    use_evolution, top_k = render_sidebar(rag, status)

    # 标签页
    tab1, tab2, tab3 = st.tabs(["💬 问答", "📚 知识库", "🔄 进化引擎"])

    with tab1:
        render_chat(rag, use_evolution, top_k)

    with tab2:
        render_knowledge_tab(rag)

    with tab3:
        render_evolution_tab(rag)


if __name__ == "__main__":
    main()
