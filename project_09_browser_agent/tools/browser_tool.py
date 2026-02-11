# tools/browser_tool.py — 浏览器工具集（Agent 可调用的 @tool 函数）
#
# 【职责】提供 6 个 LangChain 工具，供 plan_and_act 节点的 LLM 选择和 ToolNode 执行。
# 【两种模式】
#   默认：requests + BeautifulSoup 抓静态 HTML（无需安装浏览器）
#   USE_PLAYWRIGHT=true：真实无头浏览器（支持 JS 渲染，本项目默认未启用）
#
# 【工具列表】
#   navigate_to / get_page_text / extract_links / search_in_page
#   get_current_url / web_search_and_open
"""
支持两种模式：
1. Simulated（默认，无需安装浏览器）：使用 requests + BeautifulSoup 抓取静态页面
2. Playwright（USE_PLAYWRIGHT=true）：真实无头浏览器，支持 JS 渲染

工具列表：
- navigate_to(url)       → 导航到指定URL，返回页面标题和文本摘要
- get_page_text(url)     → 获取页面纯文本内容
- click_element(selector)→ 点击页面元素（Playwright模式）
- fill_form(selector, value) → 填写表单（Playwright模式）
- take_screenshot(filename) → 截图保存
- extract_links(url)     → 提取页面所有链接
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from loguru import logger

from config import BROWSER_TIMEOUT_MS, SCREENSHOT_DIR, USE_PLAYWRIGHT

_TIMEOUT = BROWSER_TIMEOUT_MS / 1000  # Convert ms to seconds

# Browser session state (simulated)
_SESSION_STATE: dict = {
    "current_url": None,
    "current_html": None,
    "current_title": None,
    "history": [],
}

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _validate_url(url: str) -> str:
    """
    校验 URL 安全性：仅允许 http/https，拦截 localhost 和内网地址。

    Raises:
        ValueError: URL 格式非法或为私有地址时
    """
    url = url.strip()
    if not url:
        raise ValueError("URL 不能为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的协议: {parsed.scheme!r}，仅支持 http/https")
    if not parsed.netloc:
        raise ValueError("URL 格式无效，缺少域名")
    # Block private/local addresses
    host = parsed.netloc.split(":")[0].lower()
    blocked = ("localhost", "127.", "192.168.", "10.", "172.16.", "::1")
    if any(host == b or host.startswith(b) for b in blocked):
        raise ValueError(f"出于安全考虑，禁止访问本地/私有地址: {host}")
    return url


def _fetch_page(url: str) -> tuple[str, str, str]:
    """
    抓取网页并解析：HTTP GET → BeautifulSoup 去噪 → 提取标题和正文。

    Returns:
        (title, text_summary, html) 三元组
    """
    url = _validate_url(url)
    try:
        resp = requests.get(url, headers=_REQUEST_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        raise RuntimeError(f"页面请求失败: {e}")

    soup = BeautifulSoup(html, "lxml")
    # Remove script/style noise
    for tag in soup(["script", "style", "nav", "footer", "iframe"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "无标题"
    # Extract readable text
    text = soup.get_text(separator="\n", strip=True)
    # Collapse blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return title, text, html


def _truncate(text: str, max_chars: int = 3000) -> str:
    """截断过长文本，防止超大页面导致 LLM 上下文溢出。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[内容已截断，共 {len(text)} 字符]"


# ── LangChain 工具：供 Agent 的 ToolNode 调用 ────────────────────────────────
# 所有 @tool 装饰的函数会被 bind_tools 绑定给 LLM，LLM 决定调哪个

@tool
def navigate_to(url: str) -> str:
    """导航到指定网页，返回页面标题和内容摘要；同时更新会话状态 current_url。"""
    try:
        title, text, html = _fetch_page(url)
        _SESSION_STATE.update({
            "current_url": url,
            "current_html": html,
            "current_title": title,
        })
        _SESSION_STATE["history"].append(url)
        logger.info(f"[navigate_to] {url} → {title!r}")
        return f"✅ 已导航到: {url}\n标题: {title}\n\n内容:\n{_truncate(text)}"
    except (ValueError, RuntimeError) as e:
        return f"❌ 导航失败: {e}"


@tool
def get_page_text(url: str, max_chars: int = 5000) -> str:
    """获取网页完整纯文本，适合需要详细阅读全文的场景。"""
    try:
        _, text, _ = _fetch_page(url)
        return _truncate(text, max_chars)
    except (ValueError, RuntimeError) as e:
        return f"❌ 获取文本失败: {e}"


@tool
def extract_links(url: str, filter_pattern: str = "") -> str:
    """提取页面所有链接，可选 filter_pattern 按关键词过滤。"""
    try:
        _, _, html = _fetch_page(url)
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True) or "(无文字)"
            # Convert relative to absolute
            if href.startswith("/"):
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif href.startswith("http"):
                pass
            else:
                continue  # Skip anchors, javascript:, mailto:, etc.
            if filter_pattern and filter_pattern.lower() not in href.lower() and filter_pattern.lower() not in text.lower():
                continue
            links.append(f"{text} → {href}")

        if not links:
            return f"❌ 未找到匹配的链接" + (f" (过滤词: {filter_pattern!r})" if filter_pattern else "")
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for ln in links:
            if ln not in seen:
                seen.add(ln)
                unique.append(ln)
        return f"找到 {len(unique)} 个链接:\n" + "\n".join(unique[:50])
    except (ValueError, RuntimeError) as e:
        return f"❌ 提取链接失败: {e}"


@tool
def search_in_page(query: str, url: str = "") -> str:
    """在指定页面（或当前已导航页面）中搜索包含关键词的段落。"""
    if url:
        try:
            _, text, _ = _fetch_page(url)
        except (ValueError, RuntimeError) as e:
            return f"❌ 获取页面失败: {e}"
    elif _SESSION_STATE["current_html"]:
        soup = BeautifulSoup(_SESSION_STATE["current_html"], "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    else:
        return "❌ 没有已导航的页面，请先调用 navigate_to"

    query_lower = query.lower()
    paragraphs = [p.strip() for p in text.split("\n") if p.strip() and len(p.strip()) > 20]
    matches = [p for p in paragraphs if query_lower in p.lower()]

    if not matches:
        return f"❌ 在页面中未找到包含 {query!r} 的内容"
    return f"找到 {len(matches)} 处匹配:\n\n" + "\n---\n".join(matches[:10])


@tool
def get_current_url() -> str:
    """返回当前会话已导航的页面 URL（需先调用 navigate_to）。"""
    url = _SESSION_STATE.get("current_url")
    return f"当前页面: {url}" if url else "尚未导航到任何页面"


@tool
def web_search_and_open(query: str) -> str:
    """DuckDuckGo 搜索关键词，自动打开第一个结果并返回页面摘要。"""
    # DuckDuckGo instant answer / HTML search
    search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    try:
        resp = requests.get(search_url, headers=_REQUEST_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        results = soup.find_all("a", class_="result__a")
        if not results:
            return f"未找到关于 {query!r} 的搜索结果"

        # Get first result URL
        first = results[0]
        href = first.get("href", "")
        # DuckDuckGo wraps links; extract real URL
        if "uddg=" in href:
            import urllib.parse
            parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = parsed_qs.get("uddg", [href])[0]

        title, text, html = _fetch_page(href)
        _SESSION_STATE.update({"current_url": href, "current_html": html, "current_title": title})
        _SESSION_STATE["history"].append(href)
        logger.info(f"[web_search_and_open] query={query!r} → {href}")
        return f"🔍 搜索 {query!r}\n已打开: {href}\n标题: {title}\n\n{_truncate(text, 2000)}"
    except (ValueError, RuntimeError, requests.RequestException) as e:
        return f"❌ 搜索失败: {e}"


# 导出给 agent.py 的 ToolNode 使用
BROWSER_TOOLS = [
    navigate_to,
    get_page_text,
    extract_links,
    search_in_page,
    get_current_url,
    web_search_and_open,
]
