"""
tools/datetime_tool.py — 时区时间查询工具

【职责】
1. 提供 get_datetime @tool，返回指定时区的当前日期时间
2. 支持 IANA 时区名（如 Asia/Shanghai、America/Los_Angeles）

【设计原因】
1. LLM 训练数据不含「此刻」的实时时间，必须走工具
2. zoneinfo 是 Python 3.9+ 标准库，无需额外依赖
"""
from datetime import datetime, timezone
import zoneinfo
from langchain_core.tools import tool
from loguru import logger


@tool
def get_datetime(timezone_name: str = "UTC") -> str:
    """Get the current date and time in a given timezone.
    Input: timezone name (e.g. 'UTC', 'America/Los_Angeles', 'Asia/Shanghai').
    Returns: current datetime string.
    """
    try:
        # 根据 IANA 时区名构造 tzinfo 对象
        tz = zoneinfo.ZoneInfo(timezone_name)
        now = datetime.now(tz)
        # 格式化为人类可读字符串，含时区缩写
        result = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"[datetime] {timezone_name} → {result}")
        return result
    except Exception as e:
        # 无效时区名时返回错误，Agent 可提示用户修正
        return f"Error: invalid timezone '{timezone_name}'. {e}"
