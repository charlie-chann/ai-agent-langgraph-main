# tools/calculator_tool.py — Safe math expression evaluator
import ast
import operator
from langchain_core.tools import tool
from loguru import logger

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node):
    """Recursively evaluate an AST node using only safe arithmetic ops."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _ALLOWED_OPS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _ALLOWED_OPS[op_type](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely (no code execution).
    Supports: +, -, *, /, **, %, //
    Examples: "2 ** 10", "(3.14 * 5**2)", "100 / 7"
    """
    expression = expression.strip()[:200]
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        logger.info(f"[calculator] {expression!r} = {result}")
        return str(result)
    except Exception as e:
        logger.warning(f"[calculator] error: {e}")
        return f"Calculation error: {e}"
