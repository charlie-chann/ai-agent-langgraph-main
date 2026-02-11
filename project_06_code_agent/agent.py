# agent.py — Code / DevOps Agent using LangChain ReAct
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from langchain_community.llms import Ollama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from loguru import logger

from config import OLLAMA_BASE_URL, CODE_MODEL, TEMPERATURE, AGENT_MAX_ITERATIONS
from prompts.code_prompts import CODE_REACT_TEMPLATE
from tools.code_executor import execute_python, lint_python
from tools.code_reviewer import review_code
from tools.file_tool import read_code_file, write_code_file, list_workspace_files
from tools.git_tool import git_status, git_log, git_diff, git_init_and_commit

# ── Available tools ──────────────────────────────────────────────────────────
ALL_TOOLS = [
    execute_python,
    lint_python,
    review_code,
    read_code_file,
    write_code_file,
    list_workspace_files,
    git_status,
    git_log,
    git_diff,
    git_init_and_commit,
]

# Tool names string for prompt
_TOOL_NAMES = ", ".join(t.name for t in ALL_TOOLS)
_TOOL_DESCS = "\n".join(f"{t.name}: {t.description}" for t in ALL_TOOLS)


def build_agent(model: str | None = None) -> AgentExecutor:
    """Build and return a ReAct AgentExecutor for the code agent."""
    llm = Ollama(
        model=model or CODE_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )

    prompt = PromptTemplate.from_template(
        CODE_REACT_TEMPLATE.format(tool_names=_TOOL_NAMES, tools=_TOOL_DESCS)
    )

    agent = create_react_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=AGENT_MAX_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


def run_agent(task: str, model: str | None = None) -> dict:
    """Run the code agent on a task and return result dict."""
    executor = build_agent(model)
    logger.info(f"[code_agent] task={task!r}")
    result = executor.invoke({"input": task})
    return {
        "output": result.get("output", ""),
        "steps": result.get("intermediate_steps", []),
    }


def stream_agent(task: str, model: str | None = None):
    """Stream the code agent, yielding token strings."""
    executor = build_agent(model)
    for event in executor.stream({"input": task}):
        if "output" in event:
            yield event["output"]
        elif "messages" in event:
            for msg in event["messages"]:
                if hasattr(msg, "content"):
                    yield msg.content
