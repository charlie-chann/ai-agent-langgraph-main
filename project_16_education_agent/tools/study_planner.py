# tools/study_planner.py — 学习规划工具
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from config import DEFAULT_STUDY_DAYS, MIN_DAILY_MINUTES, MAX_DAILY_MINUTES, PASS_SCORE_PCT


# 学科知识点库（简化）
_SUBJECT_TOPICS: dict[str, list[str]] = {
    "高中数学": ["函数与导数", "三角函数", "数列", "立体几何", "解析几何", "概率统计", "复数"],
    "高中物理": ["力学", "运动学", "电磁学", "热学", "光学", "原子物理"],
    "高中化学": ["元素化学", "有机化学", "化学键", "氧化还原", "化学平衡"],
    "英语": ["词汇", "语法", "阅读理解", "写作", "听力"],
    "Python编程": ["基础语法", "数据结构", "函数", "面向对象", "标准库", "异常处理"],
    "数据结构": ["数组", "链表", "栈与队列", "树与图", "排序算法", "动态规划"],
}

# 难度系数（影响每个主题所需学习时间）
_DIFFICULTY_HOURS: dict[str, float] = {
    "高中数学": 2.0, "高中物理": 1.8, "高中化学": 1.5,
    "英语": 1.0, "Python编程": 1.5, "数据结构": 2.0,
}


@dataclass
class StudyPlan:
    """个性化学习计划。"""
    student_name: str
    subject: str
    start_date: str
    end_date: str
    daily_minutes: int
    total_sessions: int
    topics_schedule: list[dict]
    milestones: list[dict]

    def to_dict(self) -> dict:
        return {
            "学生姓名": self.student_name,
            "科目": self.subject,
            "开始日期": self.start_date,
            "结束日期": self.end_date,
            "每日学习分钟": self.daily_minutes,
            "总学习次数": self.total_sessions,
            "主题进度表": self.topics_schedule,
            "里程碑": self.milestones,
        }


def generate_study_plan(
    student_name: str,
    subject: str,
    current_level: str = "beginner",  # "beginner" | "intermediate" | "advanced"
    daily_minutes: int = 60,
    target_days: int | None = None,
    weak_topics: list[str] | None = None,
) -> StudyPlan:
    """
    生成个性化学习计划。

    Args:
        student_name: 学生姓名
        subject: 学习科目
        current_level: 当前水平
        daily_minutes: 每日学习时间（分钟）
        target_days: 目标完成天数
        weak_topics: 薄弱知识点（这些会被优先安排）

    Returns:
        StudyPlan
    """
    import re
    student_name = re.sub(r'[<>"\']', '', student_name)[:30]
    subject = subject[:50]
    daily_minutes = max(MIN_DAILY_MINUTES, min(MAX_DAILY_MINUTES, daily_minutes))

    if target_days is None:
        target_days = DEFAULT_STUDY_DAYS

    topics = _SUBJECT_TOPICS.get(subject, ["基础知识", "进阶知识", "综合练习"])
    difficulty_hours = _DIFFICULTY_HOURS.get(subject, 1.5)

    # 根据水平调整难度系数
    level_multiplier = {"beginner": 1.5, "intermediate": 1.0, "advanced": 0.7}.get(current_level, 1.0)
    total_minutes_needed = len(topics) * difficulty_hours * 60 * level_multiplier

    # 计算实际天数
    actual_days = math.ceil(total_minutes_needed / daily_minutes)
    actual_days = min(actual_days, target_days)

    start_date = date.today()
    end_date = start_date + timedelta(days=actual_days)

    # 薄弱点优先排列
    if weak_topics:
        topics = [t for t in topics if any(w in t for w in weak_topics)] + \
                 [t for t in topics if not any(w in t for w in weak_topics)]

    # 均匀分配主题到各天
    topics_per_day = max(1, math.ceil(len(topics) / actual_days))
    schedule = []
    current_day = start_date
    for i in range(0, len(topics), topics_per_day):
        chunk = topics[i:i + topics_per_day]
        schedule.append({
            "日期": str(current_day),
            "学习主题": chunk,
            "预计分钟": daily_minutes,
        })
        current_day += timedelta(days=1)

    # 生成里程碑（每1/4进度一个）
    milestones = []
    for q in range(1, 5):
        milestone_day = start_date + timedelta(days=int(actual_days * q / 4))
        milestone_idx = int(len(topics) * q / 4)
        milestones.append({
            "日期": str(milestone_day),
            "目标": f"完成 {q * 25}% 学习内容（前{milestone_idx}个主题）",
            "考核方式": "阶段测验",
        })

    return StudyPlan(
        student_name=student_name,
        subject=subject,
        start_date=str(start_date),
        end_date=str(end_date),
        daily_minutes=daily_minutes,
        total_sessions=len(schedule),
        topics_schedule=schedule,
        milestones=milestones,
    )


@dataclass
class QuizQuestion:
    """测验题目数据类。"""
    question_id: str
    subject: str
    topic: str
    difficulty: str
    question_text: str
    options: list[str]
    correct_answer: str      # "A" | "B" | "C" | "D"
    explanation: str

    def to_dict(self) -> dict:
        return {
            "题号": self.question_id,
            "科目": self.subject,
            "知识点": self.topic,
            "难度": self.difficulty,
            "题目": self.question_text,
            "选项": self.options,
            "正确答案": self.correct_answer,
            "解析": self.explanation,
        }


# 预置题库（简化示例）
_QUESTION_BANK: list[dict] = [
    {"subject": "Python编程", "topic": "基础语法", "difficulty": "easy",
     "question": "以下哪个是 Python 的合法变量名？",
     "options": ["A. 2var", "B. var_2", "C. var-2", "D. class"],
     "answer": "B", "explanation": "变量名必须以字母或下划线开头，不能包含连字符，不能是关键字。"},
    {"subject": "Python编程", "topic": "数据结构", "difficulty": "medium",
     "question": "Python 列表和元组的主要区别是什么？",
     "options": ["A. 列表有序，元组无序", "B. 列表可变，元组不可变",
                 "C. 列表支持索引，元组不支持", "D. 列表只能存数字"],
     "answer": "B", "explanation": "列表(list)是可变序列，元组(tuple)是不可变序列。"},
    {"subject": "数据结构", "topic": "排序算法", "difficulty": "medium",
     "question": "快速排序的平均时间复杂度是？",
     "options": ["A. O(n)", "B. O(n log n)", "C. O(n²)", "D. O(log n)"],
     "answer": "B", "explanation": "快速排序平均时间复杂度为 O(n log n)，最坏情况 O(n²)。"},
    {"subject": "高中数学", "topic": "函数与导数", "difficulty": "medium",
     "question": "函数 f(x) = x³ 的导数 f'(x) 是？",
     "options": ["A. 3x", "B. 3x²", "C. x²", "D. 3x³"],
     "answer": "B", "explanation": "根据幂函数求导公式 (xⁿ)' = nxⁿ⁻¹，故 (x³)' = 3x²。"},
    {"subject": "英语", "topic": "语法", "difficulty": "easy",
     "question": "Which sentence is grammatically correct?",
     "options": ["A. She go to school.", "B. She goes to school.", "C. She going to school.", "D. She gone to school."],
     "answer": "B", "explanation": "第三人称单数现在时需要动词加 -s/-es。"},
]


def generate_quiz(subject: str, topic: str | None = None,
                  difficulty: str = "medium", count: int = 3) -> list[dict]:
    """
    从题库中生成测验题目。

    Args:
        subject: 科目
        topic: 知识点（可选）
        difficulty: 难度 easy/medium/hard
        count: 题目数量

    Returns:
        list[dict]: 题目列表
    """
    pool = [q for q in _QUESTION_BANK if q["subject"] == subject]
    if topic:
        pool = [q for q in pool if q["topic"] == topic] or pool
    pool = [q for q in pool if q["difficulty"] == difficulty] or pool

    # 取前 count 道（生产环境应随机抽取）
    selected = pool[:count]
    result = []
    for i, q in enumerate(selected):
        result.append(QuizQuestion(
            question_id=f"Q{i+1:03d}",
            subject=q["subject"],
            topic=q["topic"],
            difficulty=q["difficulty"],
            question_text=q["question"],
            options=q["options"],
            correct_answer=q["answer"],
            explanation=q["explanation"],
        ).to_dict())
    return result


def score_quiz(questions: list[dict], answers: dict[str, str]) -> dict:
    """
    批改测验答案，返回得分报告。

    Args:
        questions: 题目列表（generate_quiz 返回的格式）
        answers: 学生答案 {question_id: answer}

    Returns:
        dict: 得分报告
    """
    total = len(questions)
    correct = 0
    details = []
    for q in questions:
        qid = q["题号"]
        std_ans = q["正确答案"]
        student_ans = answers.get(qid, "")
        is_correct = student_ans.upper() == std_ans.upper()
        if is_correct:
            correct += 1
        details.append({
            "题号": qid,
            "知识点": q["知识点"],
            "学生答案": student_ans,
            "正确答案": std_ans,
            "是否正确": is_correct,
            "解析": q.get("解析", ""),
        })

    score_pct = (correct / total * 100) if total > 0 else 0
    return {
        "总题数": total,
        "正确数": correct,
        "得分率": round(score_pct, 1),
        "是否及格": score_pct >= PASS_SCORE_PCT,
        "详情": details,
    }
