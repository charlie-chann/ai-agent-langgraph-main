# project_24_openclaw_twitter — Twitter/X Content Agent

## Business Value

Twitter/X has 238M daily active users globally, primarily English-speaking tech, finance, and media professionals. Key pain points:
- **280-character constraint**: Condensing complex ideas into 280 chars is a craft that takes significant practice
- **Thread structure**: Viral threads need hook → value → CTA — hard to get right consistently
- **Hashtag overuse**: Many creators spam hashtags; Twitter's algorithm actually penalizes >3 hashtags per tweet
- **Timezone optimization**: Posting at the wrong time (e.g., 2am EST for US tech audience) wastes even great content

This Agent handles all of the above automatically, including tweet generation, thread structuring, optimal UTC scheduling, and evidence-based hashtag selection.

## Project Summary

Twitter/X AI Content Agent supporting single tweet generation (≤280 chars), multi-tweet threads (up to 20), hashtag optimization (max 3, algorithm-friendly), and UTC-based posting schedule.

## Technical Architecture

```
User Input (topic / keywords / style / thread length)
    ↓
content_generator.py  → Tweet:  hook + body + 3 hashtags (≤280 chars enforced)
                         Thread: hook → key points → CTA (numbered N/total)
tag_optimizer.py       → Twitter hashtag pool (15 tags, heat scores up to 95k)
                         Max 3 per tweet (algorithm best practice)
schedule_tool.py       → UTC-based schedule (13/15/17/20 UTC = US peak hours)
    ↓
agent.py (temperature=0.7) → Unified dispatch + _sanitize()
    ↓
app.py (Streamlit)     ← Single Tweet / Thread / Hashtags / Schedule tabs
api.py (FastAPI+SSE)   ← REST API
```

## Features

- ✅ Single tweet generation with 4 styles: informative / engaging / promotional / thread_hook
- ✅ Thread generation: hook + N key points + CTA (auto-numbered)
- ✅ Hard 280-char enforcement on every tweet
- ✅ Max 3 hashtags (Twitter algorithm recommendation)
- ✅ UTC-based scheduling (aligned to US business hours)
- ✅ Compliance check (filters prohibited words like "gambling", "scam")
- ✅ SSE streaming AI strategy chat

## Setup

```bash
cd project_24_openclaw_twitter
uv run streamlit run app.py
# API:
uv run uvicorn api:app --port 8024 --reload
```

## API Reference

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | /health | - | Health check |
| POST | /generate/tweet | topic, keywords, style | Single tweet ≤280 chars |
| POST | /generate/thread | topic, points, num_tweets | Multi-tweet thread |
| POST | /tags | topic, keywords | Hashtag recommendations |
| POST | /schedule | posts | UTC posting schedule |
| POST | /chat/stream | message | SSE streaming chat |

## Tests

```bash
uv run pytest tests/ -v
# 35/35 ✅
```

## Benchmarks

| Metric | Value |
|--------|-------|
| Tweet char enforcement | 100% within 280 |
| Thread hook presence | Always present |
| Hashtag count compliance | ≤3 always |
| Test pass rate | 35/35 (100%) |

## Roadmap

- [ ] OAuth integration with Twitter API v2 (direct post scheduling)
- [ ] Engagement analytics (likes/retweets prediction model)
- [ ] Multi-language support beyond English
- [ ] A/B test different hook styles
- [ ] Rate limiting for API-safe posting
