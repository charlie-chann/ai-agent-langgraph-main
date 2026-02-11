# tools/content_generator.py — Twitter/X 推文与长线程生成
from __future__ import annotations

import re
from dataclasses import dataclass, field
from config import MAX_TWEET_LENGTH, MAX_THREAD_TWEETS, MAX_HASHTAGS, PLATFORM, PROHIBITED_WORDS_CHECK


_PROHIBITED_WORDS = ["gambling", "scam", "fraud", "fake"]

_TOPIC_HASHTAGS: dict[str, list[str]] = {
    "AI": ["AI", "MachineLearning", "DeepLearning", "OpenAI", "LLM"],
    "Tech": ["Tech", "Software", "Programming", "Developer", "OpenSource"],
    "Python": ["Python", "Coding", "DataScience", "PyDev", "100DaysOfCode"],
    "Startup": ["Startup", "Entrepreneur", "SaaS", "BuildInPublic", "IndieHacker"],
    "Productivity": ["Productivity", "GTD", "DeepWork", "Habits", "Mindset"],
    "Finance": ["Finance", "Investing", "PersonalFinance", "Wealth", "StockMarket"],
    "Career": ["Career", "JobHunting", "Interview", "Leadership", "WorkLife"],
}

_HOOK_TEMPLATES = [
    "Most people get {topic} wrong. Here's what actually works:",
    "I spent 6 months studying {topic}. Here's what I learned (thread 🧵):",
    "3 hard truths about {topic} nobody talks about:",
    "{topic} changed everything for me. Here's how:",
    "Stop wasting time on {topic}. Do this instead:",
]


@dataclass
class Tweet:
    """单条推文。"""
    text: str
    char_count: int
    hashtags: list[str]
    compliance_check: dict

    def to_dict(self) -> dict:
        return {
            "平台": PLATFORM,
            "内容": self.text,
            "字符数": self.char_count,
            "标签": self.hashtags,
            "合规检查": self.compliance_check,
        }


@dataclass
class TwitterThread:
    """推文长线程。"""
    topic: str
    tweets: list[str]   # 每条推文文本
    total_tweets: int
    hashtags: list[str]
    compliance_check: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        numbered = [f"{i+1}/{self.total_tweets} {t}" for i, t in enumerate(self.tweets)]
        return {
            "平台": PLATFORM,
            "话题": self.topic,
            "总条数": self.total_tweets,
            "推文列表": numbered,
            "标签": self.hashtags,
            "合规检查": self.compliance_check,
        }


def _check_compliance(text: str) -> dict:
    violations = [w for w in _PROHIBITED_WORDS if w.lower() in text.lower()] if PROHIBITED_WORDS_CHECK else []
    return {"passed": len(violations) == 0, "violations": violations}


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    return re.sub(r'<[^>]+>', '', text)


def generate_tweet(topic: str, keywords: list[str] | None = None,
                   style: str = "informative") -> Tweet:
    """生成单条推文（≤280字符）。"""
    topic = _sanitize(topic)[:50]
    keywords = [_sanitize(k)[:20] for k in (keywords or [])[:3]]
    kw_str = ", ".join(keywords) if keywords else topic

    style_content = {
        "informative": f"Quick tip about {topic}: focus on {kw_str} to get the best results. Consistency beats perfection every time.",
        "engaging": f"Hot take: {topic} is the most underrated skill in tech right now. Anyone else working on {kw_str}? Drop a 👇 if yes!",
        "promotional": f"Just shipped a new update on {topic}! Key improvements: {kw_str}. Check it out and let me know what you think 🚀",
        "thread_hook": _HOOK_TEMPLATES[len(topic) % len(_HOOK_TEMPLATES)].format(topic=topic),
    }
    body = style_content.get(style, style_content["informative"])

    # 添加标签
    tags = _TOPIC_HASHTAGS.get(topic, ["Tech", "AI"])[:MAX_HASHTAGS]
    tag_str = " ".join(f"#{t}" for t in tags)
    full = f"{body} {tag_str}"

    # 确保不超过 280 字符
    if len(full) > MAX_TWEET_LENGTH:
        max_body = MAX_TWEET_LENGTH - len(tag_str) - 1
        body = body[:max_body - 1] + "…"
        full = f"{body} {tag_str}"

    compliance = _check_compliance(full)
    return Tweet(text=full, char_count=len(full), hashtags=tags, compliance_check=compliance)


def generate_thread(topic: str, points: list[str] | None = None,
                    num_tweets: int = 5) -> TwitterThread:
    """生成推文线程（多条连续推文）。"""
    topic = _sanitize(topic)[:50]
    num_tweets = min(num_tweets, MAX_THREAD_TWEETS)

    # 默认要点
    if not points:
        points = [
            f"Point {i+1}: Key insight about {topic}" for i in range(num_tweets - 2)
        ]

    tweets_text: list[str] = []

    # 开场钩子
    hook = _HOOK_TEMPLATES[len(topic) % len(_HOOK_TEMPLATES)].format(topic=topic)
    tweets_text.append(hook[:MAX_TWEET_LENGTH])

    # 中间内容
    for i, point in enumerate(points[:num_tweets - 2]):
        point_clean = _sanitize(str(point))
        tweet = f"{i+2}) {point_clean}"
        if len(tweet) > MAX_TWEET_LENGTH:
            tweet = tweet[:MAX_TWEET_LENGTH - 1] + "…"
        tweets_text.append(tweet)

    # 结尾 CTA
    cta = f"That's a wrap! If you found this useful, RT the first tweet so others can learn too. Follow for more {topic} content 💡"
    tweets_text.append(cta[:MAX_TWEET_LENGTH])

    # 补足到 num_tweets
    while len(tweets_text) < num_tweets:
        idx = len(tweets_text) + 1
        tweets_text.append(f"{idx}) More insights on {topic} coming soon…"[:MAX_TWEET_LENGTH])

    tags = _TOPIC_HASHTAGS.get(topic, ["Tech", "AI"])[:MAX_HASHTAGS]
    compliance = _check_compliance(" ".join(tweets_text))

    return TwitterThread(
        topic=topic,
        tweets=tweets_text[:num_tweets],
        total_tweets=min(num_tweets, len(tweets_text)),
        hashtags=tags,
        compliance_check=compliance,
    )
