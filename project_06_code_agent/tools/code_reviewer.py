# tools/code_reviewer.py — LLM-powered code review tool
from langchain_core.tools import tool
from loguru import logger


@tool
def review_code(code: str, language: str = "python") -> str:
    """Perform a security and quality review of the provided code.
    Args:
        code: source code to review
        language: programming language (python, javascript, bash)
    Returns: structured review with issues and suggestions.
    """
    from langchain_community.chat_models import ChatOllama
    from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
    from prompts.code_prompts import review_prompt

    code = code.strip()[:5000]
    language = language.lower() if language.lower() in {"python", "javascript", "bash", "typescript"} else "python"

    if not code:
        return "Error: empty code provided."

    try:
        llm = ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)
        chain = review_prompt | llm
        result = chain.invoke({"code": code, "language": language})
        logger.info(f"[review_code] {language} code reviewed ({len(code)} chars)")
        return result.content
    except Exception as e:
        logger.error(f"[review_code] error: {e}")
        return f"Review failed: {e}"


@tool
def generate_tests(code: str, framework: str = "pytest") -> str:
    """Generate unit tests for the provided Python code.
    Args:
        code: Python source code to test
        framework: pytest | unittest
    Returns: generated test code.
    """
    from langchain_community.chat_models import ChatOllama
    from langchain_core.prompts import ChatPromptTemplate
    from config import OLLAMA_BASE_URL, DEFAULT_MODEL

    code = code.strip()[:4000]
    if not code:
        return "Error: empty code."

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are a test engineer. Generate thorough {framework} tests for the provided Python code.
Include: happy path, edge cases, error cases. Use mocks where needed. Return only the test code."""),
        ("human", "Generate tests for:\n\n```python\n{code}\n```"),
    ])
    try:
        llm = ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.1)
        result = (prompt | llm).invoke({"code": code})
        return result.content
    except Exception as e:
        return f"Test generation failed: {e}"
