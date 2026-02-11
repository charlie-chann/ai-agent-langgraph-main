"""早报生成 Agent 配置"""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.3

# 早报配置
MAX_BRIEF_LENGTH = 3000      # 早报正文最大字符
MAX_ARTICLES_PER_SOURCE = 5  # 每个 RSS 源最多取文章数
MAX_SOURCES = 10             # 最多处理 RSS 源数
SUMMARY_MAX_LENGTH = 200     # 每条新闻摘要最大字符
TOP_STORIES_COUNT = 8        # 精选头条数量

PLATFORM = "morning_brief"

# 早报分类
CATEGORIES = ["国际要闻", "科技动态", "财经市场", "国内新闻", "其他"]

# 默认 RSS 源（可被 data/rss-sources.json 覆盖）
DEFAULT_RSS_SOURCES = [
    {
        "name": "BBC国际",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "tags": ["国际", "新闻"],
        "category": "国际要闻"
    },
    {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "tags": ["科技", "创业"],
        "category": "科技动态"
    },
    {
        "name": "联合早报",
        "url": "https://www.zaobao.com.sg/rss/realtime/china",
        "tags": ["中国", "国际"],
        "category": "国内新闻"
    }
]

# 推送时间（每天早报推送时间，24小时制）
BRIEF_SEND_HOUR = 7
BRIEF_SEND_MINUTE = 30

# 输出格式
OUTPUT_FORMATS = ["markdown", "plain", "html"]
DEFAULT_OUTPUT_FORMAT = "markdown"

# 报告保存路径（相对于项目目录）
REPORTS_DIR = "reports"
