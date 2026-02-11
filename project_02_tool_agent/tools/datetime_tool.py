# tools/datetime_tool.py — Current time & date utilities
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
        tz = zoneinfo.ZoneInfo(timezone_name)
        now = datetime.now(tz)
        result = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"[datetime] {timezone_name} → {result}")
        return result
    except Exception as e:
        return f"Error: invalid timezone '{timezone_name}'. {e}"
