# tests/test_agent.py — project_02_tool_agent
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_calculator_basic():
    from tools.calculator_tool import calculator
    assert calculator.invoke("2 + 2") == "4"
    assert calculator.invoke("10 ** 3") == "1000"
    assert calculate_float("10 / 3")


def calculate_float(expr):
    from tools.calculator_tool import calculator
    result = calculator.invoke(expr)
    return float(result) > 0


def test_calculator_injection_blocked():
    from tools.calculator_tool import calculator
    result = calculator.invoke("__import__('os').system('echo pwned')")
    assert "error" in result.lower() or "unsupported" in result.lower()


def test_file_sandbox():
    from tools.file_tool import file_write, file_read, SANDBOX
    file_write.invoke({"filename": "test_sandbox.txt", "content": "hello"})
    content = file_read.invoke("test_sandbox.txt")
    assert content == "hello"


def test_file_path_traversal_blocked():
    from tools.file_tool import file_read
    result = file_read.invoke("../../../etc/passwd")
    assert "error" in result.lower() or "blocked" in result.lower()


def test_datetime_utc():
    from tools.datetime_tool import get_datetime
    result = get_datetime.invoke("UTC")
    assert "UTC" in result or "2" in result  # has a year/date


def test_datetime_invalid_tz():
    from tools.datetime_tool import get_datetime
    result = get_datetime.invoke("Mars/Olympus")
    assert "error" in result.lower() or "invalid" in result.lower()
