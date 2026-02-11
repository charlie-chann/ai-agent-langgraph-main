"""
tools/calculator_tool.py — 安全数学表达式计算器

【职责】
1. 提供 @tool 装饰的 calculator 函数，供 ReAct Agent 调用
2. 用 AST 白名单解析表达式，禁止 eval() 执行任意代码

【设计原因】
1. LLM 心算大数/浮点容易错，必须走专用工具
2. 普通 eval() 有代码注入风险；AST 只允许 + - * / ** % // 等算术运算
3. docstring 会发给 LLM 作为工具说明，必须写清支持的操作符和示例
"""
import ast
import operator
from langchain_core.tools import tool
from loguru import logger

# AST 节点类型 → Python 运算符的映射（白名单，之外的运算符一律拒绝）
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
    """
    递归遍历 AST 节点，仅执行白名单内的算术运算。

    参数:
        node: ast 模块解析后的表达式节点

    返回:
        计算结果的 Python 数值

    说明:
        无 @tool 装饰，仅 calculator 内部调用，LLM 不可直接访问。
    """
    # 叶子节点：数字常量，如 42、3.14
    if isinstance(node, ast.Constant):
        return node.value
    # 二元运算：如 a + b、a ** b
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _ALLOWED_OPS[op_type](left, right)
    # 一元运算：如 -5
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
    # 截断过长输入，防止恶意超长表达式拖慢解析
    expression = expression.strip()[:200]
    try:
        # mode="eval"：只解析单个表达式，不允许语句块
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        logger.info(f"[calculator] {expression!r} = {result}")
        return str(result)
    except Exception as e:
        logger.warning(f"[calculator] error: {e}")
        # 返回可读错误信息，Agent 可据此 Retry 或告知用户
        return f"Calculation error: {e}"
