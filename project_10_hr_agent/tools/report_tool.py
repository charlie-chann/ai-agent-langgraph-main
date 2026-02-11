# tools/report_tool.py — HR screening report generator
"""
生成招聘筛选报告，支持按批次生成和导出。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from langchain_core.tools import tool
from loguru import logger

from config import REPORTS_DIR


def _ensure_dir() -> Path:
    d = Path(REPORTS_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


@tool
def generate_screening_report(position: str, results_json: str) -> str:
    """根据筛选结果生成 Markdown 格式的招聘报告。
    Args:
        position: 招聘职位名称
        results_json: 筛选结果JSON（list of ScoringResult.to_dict()）
    Returns: Markdown 格式报告文本
    """
    try:
        results = json.loads(results_json)
        if not isinstance(results, list):
            return "❌ results_json 必须是列表格式"
    except json.JSONDecodeError as e:
        return f"❌ JSON解析失败: {e}"

    shortlist = [r for r in results if r.get("decision") == "shortlist"]
    review = [r for r in results if r.get("decision") == "review"]
    reject = [r for r in results if r.get("decision") == "reject"]

    lines = [
        f"# 招聘筛选报告 — {position}",
        f"*生成时间: {time.strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## 汇总统计",
        f"| 状态 | 数量 | 占比 |",
        f"|------|------|------|",
        f"| ✅ 入围 | {len(shortlist)} | {len(shortlist)/max(len(results),1)*100:.0f}% |",
        f"| ⚠️ 待定 | {len(review)} | {len(review)/max(len(results),1)*100:.0f}% |",
        f"| ❌ 淘汰 | {len(reject)} | {len(reject)/max(len(results),1)*100:.0f}% |",
        f"| 合计 | {len(results)} | 100% |",
        "",
        "## 入围候选人",
    ]

    if shortlist:
        for r in shortlist:
            lines.extend([
                f"### {r['candidate_name']} (ID: {r['candidate_id']})",
                f"- **综合评分**: {r['total_score']:.2f}",
                f"- **技能匹配**: {r['skill_score']:.2f}  **经验**: {r['experience_score']:.2f}  **学历**: {r['education_score']:.2f}",
                f"- **匹配技能**: {', '.join(r.get('matched_skills', [])[:8]) or '—'}",
                f"- **缺少技能**: {', '.join(r.get('missing_skills', [])[:5]) or '—'}",
                "",
            ])
    else:
        lines.append("*暂无入围候选人*\n")

    lines.append("## 待定候选人")
    if review:
        for r in review:
            lines.extend([
                f"- **{r['candidate_name']}** (ID: {r['candidate_id']}) — 评分 {r['total_score']:.2f}, 建议: {'; '.join(r.get('notes', [])[:2]) or '—'}",
            ])
    else:
        lines.append("*无待定候选人*")

    lines.extend([
        "",
        "## 筛选建议",
        f"- 建议优先面试 {len(shortlist)} 位入围候选人",
        f"- {len(review)} 位待定候选人可考虑补充技能培训后录用",
        f"- {len(reject)} 位候选人不符合基本要求",
    ])

    report = "\n".join(lines)

    # Save to file
    output_dir = _ensure_dir()
    filename = f"screening_{position.replace(' ', '_')}_{int(time.time())}.md"
    output_path = output_dir / filename
    output_path.write_text(report, encoding="utf-8")
    logger.info(f"[generate_report] Saved to {output_path}")

    return report


@tool
def list_reports() -> str:
    """列出所有已生成的招聘报告。
    Returns: 报告文件列表（JSON格式）
    """
    output_dir = _ensure_dir()
    files = sorted(output_dir.glob("screening_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return json.dumps({"found": False, "message": "暂无报告"}, ensure_ascii=False)
    result = [{"filename": f.name, "size_kb": round(f.stat().st_size / 1024, 1)} for f in files[:20]]
    return json.dumps({"found": True, "count": len(result), "reports": result}, ensure_ascii=False, indent=2)
