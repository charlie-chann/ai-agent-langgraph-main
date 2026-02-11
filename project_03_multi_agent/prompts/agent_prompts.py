# prompts/agent_prompts.py — all agent role prompts for project_03
from langchain_core.prompts import ChatPromptTemplate

# ── Planner ────────────────────────────────────────────────────────────────────
PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strategic task planner. Break down the user's request
into a structured plan with clear research questions and content goals.

Output a JSON object with:
{{
  "goal": "one sentence goal",
  "research_questions": ["q1", "q2", ...],
  "content_sections": ["section1", "section2", ...],
  "tone": "professional|casual|persuasive",
  "target_audience": "describe the audience"
}}

Respond ONLY with the JSON object."""),
    ("human", "Task: {task}\nScenario: {scenario}"),
])

# ── Researcher ─────────────────────────────────────────────────────────────────
RESEARCHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a thorough researcher. Using the search results provided,
extract and synthesize the most relevant facts, statistics, and insights for each
research question. Be concise but comprehensive. Cite sources when possible."""),
    ("human", """Research questions:
{research_questions}

Search results:
{search_results}

Provide structured research findings in markdown."""),
])

# ── Writer ─────────────────────────────────────────────────────────────────────
WRITER_MARKET_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert market research analyst and writer.
Write a professional market research report based on the plan and research findings.
Structure: Executive Summary → Market Overview → Key Findings → Analysis → Recommendations.
Tone: {tone}. Target audience: {target_audience}.
Use markdown with headers, bullet points, and data tables where appropriate."""),
    ("human", """Plan:
{plan}

Research findings:
{research}

Write the full report."""),
])

WRITER_SOCIAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a creative social media content strategist.
Create engaging, platform-optimized content based on the plan and research.
Include: Hook → Core message → Call to action → Hashtags.
Tone: {tone}. Target audience: {target_audience}.
Create content for: LinkedIn post, Twitter/X thread (5 tweets), Instagram caption."""),
    ("human", """Plan:
{plan}

Research findings:
{research}

Write the social media content."""),
])

# ── Critic ─────────────────────────────────────────────────────────────────────
CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strict quality critic. Evaluate the content on:
1. Accuracy & factual correctness (1-10)
2. Clarity & structure (1-10)
3. Relevance to goal (1-10)
4. Actionability (1-10)

Respond ONLY with JSON:
{{
  "overall_score": <1-10>,
  "scores": {{"accuracy": n, "clarity": n, "relevance": n, "actionability": n}},
  "strengths": ["..."],
  "improvements": ["..."],
  "verdict": "pass|revise"
}}"""),
    ("human", """Goal: {goal}

Content to evaluate:
{content}"""),
])

# ── Summarizer ─────────────────────────────────────────────────────────────────
SUMMARIZER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a concise summarizer. Create a crisp executive summary
(3-5 bullet points) of the key takeaways from the content.
End with one clear "Next Step" recommendation."""),
    ("human", "Content:\n{content}"),
])
