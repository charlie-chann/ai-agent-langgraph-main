"""报告生成器 - 将调研结果整合为结构化报告"""

import re
from dataclasses import dataclass, field
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MAX_REPORT_LENGTH, REPORT_SECTIONS
from tools.research_engine import ResearchSource, QueryResult


@dataclass
class ResearchReport:
    """深度调研报告"""
    topic: str
    depth: str
    executive_summary: str
    key_findings: list[str]
    data_analysis: str
    source_validation: dict
    contradictions: list[str]
    conclusions: str
    further_reading: list[dict]
    total_sources: int
    avg_credibility: float
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    word_count: int = 0


def compute_avg_credibility(results: list[QueryResult]) -> float:
    """计算所有来源的平均可信度"""
    all_scores = [
        s.credibility_score
        for r in results
        for s in r.sources
    ]
    return round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0


def extract_further_reading(results: list[QueryResult], max_links: int = 5) -> list[dict]:
    """提取延伸阅读链接（按可信度排序）"""
    all_sources: list[ResearchSource] = []
    for r in results:
        all_sources.extend(r.sources)

    # 去重
    seen_urls: set[str] = set()
    unique = []
    for s in all_sources:
        if s.url not in seen_urls:
            seen_urls.add(s.url)
            unique.append(s)

    ranked = sorted(unique, key=lambda s: s.credibility_score, reverse=True)
    return [{"title": s.title, "url": s.url, "credibility": s.credibility_score} for s in ranked[:max_links]]


def generate_report_markdown(report: ResearchReport) -> str:
    """生成 Markdown 格式调研报告"""
    lines = [
        f"# 深度调研报告：{report.topic}",
        f"> 调研深度: {report.depth} | 生成时间: {report.generated_at} | 来源数: {report.total_sources} | 平均可信度: {report.avg_credibility:.0%}",
        "",
        "---",
        "",
        "## 📋 执行摘要",
        "",
        report.executive_summary,
        "",
        "## 🔍 主要发现",
        ""
    ]
    for i, finding in enumerate(report.key_findings, 1):
        lines.append(f"{i}. {finding}")
    lines += [
        "",
        "## 📊 数据分析",
        "",
        report.data_analysis,
        "",
        "## ✅ 来源验证",
        ""
    ]
    validation = report.source_validation
    for point in validation.get("validated_points", []):
        lines.append(f"- ✅ {point}")
    lines += ["", "## ⚠️ 矛盾点 & 存疑信息", ""]
    if report.contradictions:
        for c in report.contradictions:
            lines.append(f"- ⚠️ {c}")
    else:
        lines.append("- 未发现明显矛盾点")
    lines += [
        "",
        "## 💡 结论",
        "",
        report.conclusions,
        "",
        "## 📚 延伸阅读",
        ""
    ]
    for link in report.further_reading:
        lines.append(f"- [{link['title']}]({link['url']}) — 可信度: {link['credibility']:.0%}")

    return "\n".join(lines)


def build_report(
    topic: str,
    depth: str,
    query_results: list[QueryResult],
    validation: dict
) -> ResearchReport:
    """从原始调研数据构建报告对象"""
    total_sources = sum(len(r.sources) for r in query_results)
    avg_credibility = compute_avg_credibility(query_results)
    further_reading = extract_further_reading(query_results)

    key_findings = [
        f"通过 {len(query_results)} 个子查询，共检索到 {total_sources} 个信息来源",
        f"所有来源平均可信度为 {avg_credibility:.0%}",
    ]
    if query_results:
        key_findings.append(f"重点发现：{query_results[0].summary[:100]}")

    report = ResearchReport(
        topic=topic,
        depth=depth,
        executive_summary=(
            f"本报告基于对「{topic}」的{depth}级别调研，"
            f"综合分析了 {total_sources} 个信息来源。"
            f"综合置信度为 {validation.get('confidence', 0):.0%}。"
        ),
        key_findings=key_findings,
        data_analysis=f"当前数据显示，{topic}领域正在经历快速变化，相关证据主要来自{total_sources}个独立来源。建议结合最新数据验证核心结论。",
        source_validation=validation,
        contradictions=validation.get("contradictions", []),
        conclusions=(
            f"综合多源信息，{topic}存在以下核心判断：\n"
            f"1. 信息整体可信度较{'高' if avg_credibility >= 0.7 else '低'}（{avg_credibility:.0%}）\n"
            f"2. 已有效交叉验证 {len(validation.get('validated_points', []))} 个关键发现\n"
            f"3. 建议关注 {len(validation.get('contradictions', []))} 个存疑点"
        ),
        further_reading=further_reading,
        total_sources=total_sources,
        avg_credibility=avg_credibility
    )
    content = generate_report_markdown(report)
    if len(content) > MAX_REPORT_LENGTH:
        report.data_analysis = report.data_analysis[:500] + "…"
    report.word_count = min(len(generate_report_markdown(report)), MAX_REPORT_LENGTH)
    return report
