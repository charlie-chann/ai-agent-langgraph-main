# app.py — HR Recruitment Agent Streamlit UI
import time
import json

import streamlit as st

st.set_page_config(
    page_title="👔 HR Recruitment Agent",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 👔 HR Recruitment Agent")
    st.markdown("*AI驱动的招聘筛选助手*")
    st.divider()

    st.markdown("### 模型配置")
    from config import DEFAULT_MODEL, OLLAMA_BASE_URL
    model_name = st.text_input("模型", value=DEFAULT_MODEL)
    ollama_url = st.text_input("Ollama URL", value=OLLAMA_BASE_URL)

    st.divider()
    st.markdown("### 功能说明")
    st.markdown("""
**核心功能：**
- 📄 简历批量筛选评分
- 🎯 多维度技能匹配
- 📊 生成招聘筛选报告
- 💬 智能 HR 对话助理
- ❓ 生成个性化面试题

**评分维度：**
- 技能匹配 50%
- 工作经验 25%
- 学历要求 15%
- 工作稳定性 10%
    """)

    st.divider()
    tab_select = st.radio("功能模式", ["💬 智能对话", "📊 批量筛选", "❓ 面试题生成"])

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("👔 HR Recruitment Agent")
st.caption("AI驱动的招聘筛选系统——公平、高效、可解释")

# ── Tab 1: Chat ───────────────────────────────────────────────────────────────
if tab_select == "💬 智能对话":
    if "hr_chat_history" not in st.session_state:
        st.session_state.hr_chat_history = []

    for msg in st.session_state.hr_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("向 HR Agent 提问（如：帮我筛选Python工程师简历）")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.hr_chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_resp = ""
            try:
                import config
                config.DEFAULT_MODEL = model_name
                config.OLLAMA_BASE_URL = ollama_url
                from agent import stream_hr_chat
                for event in stream_hr_chat(user_input, st.session_state.hr_chat_history[:-1]):
                    for node_name, node_state in event.items():
                        if node_name == "hr_agent":
                            msgs = node_state.get("messages", [])
                            if msgs:
                                content = msgs[-1].content if hasattr(msgs[-1], "content") else ""
                                if content:
                                    full_resp = content
                                    placeholder.markdown(full_resp + "▌")
                placeholder.markdown(full_resp or "（处理中...）")
            except Exception as e:
                placeholder.error(f"❌ 错误: {e}")
                full_resp = f"❌ {e}"

        st.session_state.hr_chat_history.append({"role": "assistant", "content": full_resp})

# ── Tab 2: Batch Screening ────────────────────────────────────────────────────
elif tab_select == "📊 批量筛选":
    st.subheader("批量简历筛选")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("#### 岗位要求")
        position = st.text_input("招聘职位", "高级Python工程师")
        required_skills_str = st.text_area(
            "必需技能（逗号分隔）",
            "Python,FastAPI,LangChain,PostgreSQL",
            height=80,
        )
        preferred_skills_str = st.text_area(
            "优先技能（逗号分隔）",
            "Docker,Kubernetes,AWS",
            height=80,
        )
        min_years = st.number_input("最低工作年限", 0, 20, 3)
        preferred_years = st.number_input("理想工作年限", 0, 20, 5)
        min_education = st.selectbox("最低学历", ["高中", "大专", "本科", "硕士", "博士"], index=2)

    with col2:
        st.markdown("#### 候选人简历（JSON格式）")
        sample_resumes = json.dumps([
            {"id": "R001", "name": "张伟", "skills": ["Python", "FastAPI", "LangChain", "Docker"], "years_experience": 6, "education": "硕士", "job_count": 3},
            {"id": "R002", "name": "李娜", "skills": ["Python", "Django", "PostgreSQL"], "years_experience": 4, "education": "本科", "job_count": 4},
            {"id": "R003", "name": "王芳", "skills": ["Java", "Spring", "MySQL"], "years_experience": 5, "education": "本科", "job_count": 2},
            {"id": "R004", "name": "刘洋", "skills": ["Python", "FastAPI", "LangChain", "AWS", "Kubernetes"], "years_experience": 8, "education": "博士", "job_count": 2},
            {"id": "R005", "name": "陈静", "skills": ["Python"], "years_experience": 1, "education": "大专", "job_count": 1},
        ], ensure_ascii=False, indent=2)
        resumes_input = st.text_area("简历列表（JSON）", sample_resumes, height=300)

    if st.button("🚀 开始筛选", type="primary"):
        try:
            from tools.resume_scorer import JobRequirement, batch_score
            from tools.report_tool import generate_screening_report

            job = JobRequirement(
                title=position,
                required_skills=[s.strip() for s in required_skills_str.split(",") if s.strip()],
                preferred_skills=[s.strip() for s in preferred_skills_str.split(",") if s.strip()],
                min_years_exp=min_years,
                preferred_years_exp=preferred_years,
                min_education=min_education,
            )
            resumes = json.loads(resumes_input)
            results = batch_score(resumes, job)

            st.success(f"✅ 筛选完成，共 {len(results)} 位候选人")

            # Show results table
            import pandas as pd
            df = pd.DataFrame([{
                "姓名": r.candidate_name,
                "综合评分": f"{r.total_score:.2f}",
                "决策": {"shortlist": "✅入围", "review": "⚠️待定", "reject": "❌淘汰"}[r.decision],
                "技能匹配": f"{r.skill_score:.2f}",
                "匹配技能": ", ".join(r.matched_skills[:5]),
                "缺少技能": ", ".join(r.missing_skills[:3]),
            } for r in results])
            st.dataframe(df, use_container_width=True)

            # Generate report
            report = generate_screening_report.invoke({
                "position": position,
                "results_json": json.dumps([r.to_dict() for r in results], ensure_ascii=False),
            })
            with st.expander("📋 完整筛选报告", expanded=True):
                st.markdown(report)

        except json.JSONDecodeError as e:
            st.error(f"❌ JSON格式错误: {e}")
        except Exception as e:
            st.error(f"❌ 筛选失败: {e}")

# ── Tab 3: Interview Questions ────────────────────────────────────────────────
elif tab_select == "❓ 面试题生成":
    st.subheader("个性化面试题生成")

    col1, col2 = st.columns([1, 1])
    with col1:
        iq_position = st.text_input("职位名称", "高级Python工程师")
        iq_required = st.text_area("岗位必需技能", "Python,FastAPI,LangChain,SQL", height=80)
        iq_candidate = st.text_area("候选人技能（从简历获取）", "Python,FastAPI,Docker,Redis", height=80)
        iq_years = st.number_input("候选人工作年限", 0, 30, 5)

    with col2:
        if st.button("生成面试题", type="primary"):
            with st.spinner("正在生成面试题..."):
                try:
                    import config
                    config.DEFAULT_MODEL = model_name
                    config.OLLAMA_BASE_URL = ollama_url
                    from agent import generate_interview_questions
                    questions = generate_interview_questions(
                        iq_position,
                        [s.strip() for s in iq_required.split(",") if s.strip()],
                        [s.strip() for s in iq_candidate.split(",") if s.strip()],
                        iq_years,
                    )
                    st.markdown(questions)
                except Exception as e:
                    st.error(f"❌ 生成失败: {e}")
