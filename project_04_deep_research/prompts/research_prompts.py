# prompts/research_prompts.py
from langchain_core.prompts import ChatPromptTemplate

# ── Query Generator ────────────────────────────────────────────────────────────
QUERY_GEN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research strategist. Generate {n} diverse, specific search queries
to deeply investigate the given research topic. Queries should cover different angles:
background/history, current state, key players, challenges, future trends, data/statistics.

Return ONLY a JSON array of strings: ["query1", "query2", ...]"""),
    ("human", "Research topic: {topic}\nAlready searched: {already_searched}"),
])

# ── Gap Analyzer ───────────────────────────────────────────────────────────────
GAP_ANALYZER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research quality analyst. Review the collected research and identify:
1. What has been well covered
2. Critical gaps still missing
3. Follow-up queries needed to fill gaps

Return JSON:
{{
  "coverage_score": <0.0-1.0>,
  "well_covered": ["topic1", ...],
  "gaps": ["missing_topic1", ...],
  "followup_queries": ["query1", "query2", ...],
  "ready_to_write": <true|false>
}}"""),
    ("human", """Original topic: {topic}

Research collected so far:
{research_summary}

Round: {round}/{max_rounds}"""),
])

# ── Synthesizer ────────────────────────────────────────────────────────────────
SYNTHESIZER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert researcher. Synthesize all search results into
structured research notes. Extract: key facts, statistics, expert opinions, trends.
Remove duplicates. Organize by theme. Keep source references."""),
    ("human", """Topic: {topic}

New search results (Round {round}):
{new_results}

Previous research notes:
{previous_notes}

Produce updated, unified research notes in markdown."""),
])

# ── Report Writer ──────────────────────────────────────────────────────────────
REPORT_WRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior analyst and expert report writer.
Write a comprehensive, well-structured research report based on the research notes.

Report structure:
# [Title]
## Executive Summary (3-5 key findings)
## Background & Context
## Current State Analysis
## Key Players / Stakeholders
## Challenges & Opportunities  
## Data & Statistics
## Future Outlook
## Recommendations
## References

Use markdown. Include data tables where relevant. Cite sources inline as [Source: ...].
Tone: professional, analytical, evidence-based."""),
    ("human", """Research topic: {topic}

Research notes:
{research_notes}

Write the full report."""),
])

# ── Report Polisher ────────────────────────────────────────────────────────────
POLISHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a professional editor. Polish this research report:
- Fix any logical gaps or inconsistencies
- Strengthen the executive summary
- Ensure all sections flow naturally
- Add a TL;DR (3 bullet points) at the very top
- Verify all claims are supported by the research

Return the improved full report."""),
    ("human", "Report to polish:\n{report}"),
])
