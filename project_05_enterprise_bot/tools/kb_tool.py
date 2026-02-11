# tools/kb_tool.py — Internal Knowledge Base search (mock + BM25)
from typing import List
from langchain_core.tools import tool
from loguru import logger

# Mock KB articles — replace with real Confluence/Notion API or RAG pipeline
KB_ARTICLES = [
    {"id": "KB001", "title": "VPN Setup Guide", "content": "To set up VPN: 1) Download Cisco AnyConnect 2) Enter server: vpn.company.com 3) Use your AD credentials. For issues contact IT at it@company.com"},
    {"id": "KB002", "title": "PTO Request Process", "content": "Submit PTO via BambooHR portal at hr.company.com/pto. Requires manager approval 5 days in advance. Maximum 10 days consecutive without VP approval."},
    {"id": "KB003", "title": "Expense Reimbursement", "content": "Submit expenses in Concur within 30 days. Attach receipts. Over $500 requires manager pre-approval. Reimbursement processed in 2 weeks."},
    {"id": "KB004", "title": "New Employee Onboarding Checklist", "content": "Day 1: IT equipment setup, badge, email. Week 1: Security training, HR orientation. Week 2: Team intro, system access. Contact hr@company.com for questions."},
    {"id": "KB005", "title": "IT Password Reset", "content": "Reset password at: selfservice.company.com/password. If locked out call IT hotline: 555-IT-HELP. Passwords must be 12+ chars, include uppercase, lowercase, number, symbol."},
    {"id": "KB006", "title": "Meeting Room Booking", "content": "Book meeting rooms via Outlook or rooms.company.com. Rooms A1-A5 for up to 10 people, B1-B3 for up to 30 people. Catering available via facilities@company.com."},
    {"id": "KB007", "title": "Security Incident Reporting", "content": "Report security incidents immediately to security@company.com or call 555-SECURE. Do not investigate yourself. Preserve all evidence. Response SLA: critical=1h, high=4h, medium=24h."},
    {"id": "KB008", "title": "Software License Requests", "content": "Request software through IT portal: it.company.com/software. Approval by manager required. Standard software approved in 2 days, specialized in 5 days. Budget owner must approve purchases over $500."},
]


def _bm25_search(query: str, top_k: int = 3) -> List[dict]:
    """Simple keyword-overlap search over KB articles."""
    query_tokens = set(query.lower().split())
    scored = []
    for article in KB_ARTICLES:
        text = f"{article['title']} {article['content']}".lower()
        text_tokens = set(text.split())
        score = len(query_tokens & text_tokens) / (len(query_tokens) + 1e-6)
        scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:top_k] if scored[0][0] > 0]


@tool
def search_kb(query: str) -> str:
    """Search the internal knowledge base for policies, guides, and procedures.
    Input: natural language question or keyword query.
    Returns: relevant KB article(s) content.
    """
    query = query.strip()[:300]
    if not query:
        return "Please provide a search query."

    results = _bm25_search(query, top_k=2)
    if not results:
        return f"No KB articles found for: {query!r}. Try rephrasing or contact IT/HR directly."

    parts = []
    for r in results:
        parts.append(f"**[{r['id']}] {r['title']}**\n{r['content']}")
    logger.info(f"[search_kb] query={query!r} results={[r['id'] for r in results]}")
    return "\n\n---\n\n".join(parts)
