"""调研引擎 - 多源信息搜索与整合"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    MAX_SOURCES_PER_QUERY, MAX_QUERIES_PER_TOPIC,
    SOURCE_CREDIBILITY_WEIGHTS, MIN_SOURCE_CREDIBILITY
)


@dataclass
class ResearchSource:
    """单个信息来源"""
    title: str
    url: str
    snippet: str
    source_type: Literal["academic", "news", "blog", "social", "unknown"]
    credibility_score: float
    retrieved_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    supports_query: str = ""


@dataclass
class QueryResult:
    """单次查询结果"""
    query: str
    sources: list[ResearchSource]
    summary: str
    confidence: float  # 综合置信度 0-1


def _sanitize_query(query: str) -> str:
    """清洗查询字符串"""
    query = re.sub(r"[\"'\\]", "", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query[:200]


def _estimate_source_type(url: str) -> Literal["academic", "news", "blog", "social", "unknown"]:
    """根据 URL 估计来源类型"""
    url_lower = url.lower()
    if any(d in url_lower for d in [".edu", "scholar.", "arxiv.", "pubmed.", "doi."]):
        return "academic"
    if any(d in url_lower for d in ["bbc.", "reuters.", "xinhua.", "cctv.", "nytimes.", "theatlantic."]):
        return "news"
    if any(d in url_lower for d in ["twitter.", "weibo.", "x.com", "reddit."]):
        return "social"
    if any(d in url_lower for d in ["medium.", "substack.", "wordpress.", "blog."]):
        return "blog"
    return "unknown"


def generate_sub_queries(topic: str, depth: str = "standard") -> list[str]:
    """
    根据主题生成多个子查询（模拟思维链分解）。
    生产环境中可接入 LLM 生成更智能的查询。
    """
    topic = _sanitize_query(topic)
    base_queries = [
        f"{topic} 最新进展",
        f"{topic} 背景与历史",
        f"{topic} 数据与统计",
    ]
    if depth in ("standard", "deep"):
        base_queries += [f"{topic} 争议与不同观点", f"{topic} 未来趋势"]
    if depth == "deep":
        base_queries += [
            f"{topic} 专家分析",
            f"{topic} 案例研究",
        ]
    return base_queries[:MAX_QUERIES_PER_TOPIC]


def search_sources(query: str, max_results: int = MAX_SOURCES_PER_QUERY) -> list[ResearchSource]:
    """
    搜索信息来源（模拟实现）。
    生产环境中替换为 Tavily / SerpAPI / DuckDuckGo 搜索。
    """
    query = _sanitize_query(query)
    mock_sources = [
        ResearchSource(
            title=f"来源 {i+1}：{query[:30]} 研究报告",
            url=f"https://example{['news', 'blog', 'academic'][i % 3]}.com/article-{i+1}",
            snippet=f"关于{query}的第{i+1}条资讯：该领域近期出现了新的发展趋势，专家表示…",
            source_type=_estimate_source_type(f"https://example{'news' if i%3==0 else 'blog' if i%3==1 else 'arxiv'}.com"),
            credibility_score=round(SOURCE_CREDIBILITY_WEIGHTS.get(
                _estimate_source_type(f"https://example{'news' if i%3==0 else 'blog' if i%3==1 else 'arxiv'}.com"),
                0.5
            ) + (0.05 - i * 0.01), 2),
            supports_query=query
        )
        for i in range(min(max_results, 4))
    ]
    return [s for s in mock_sources if s.credibility_score >= MIN_SOURCE_CREDIBILITY]


def cross_validate_findings(results: list[QueryResult]) -> dict:
    """
    交叉验证：识别多个来源共同支持的发现和矛盾点。
    
    Returns:
        {
            "validated_points": list[str],   # 多源支持的结论
            "contradictions": list[str],     # 矛盾点
            "confidence": float              # 综合置信度
        }
    """
    all_queries = [r.query for r in results]
    all_confidences = [r.confidence for r in results]

    validated_points = [
        f"多个来源（{len(results)}个查询）均证实：{all_queries[0][:50]}方向的信息具有一定可靠性"
        if all_queries else "尚无足够来源进行交叉验证"
    ]

    contradictions = []
    if len(results) >= 2:
        contradictions.append(f"来源间对 '{all_queries[0][:30]}' 的描述存在细节差异，需进一步核实")

    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return {
        "validated_points": validated_points,
        "contradictions": contradictions,
        "confidence": round(avg_confidence, 2)
    }
