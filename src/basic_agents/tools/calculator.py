"""安全计算器工具，基于 ast 模块解析数学表达式"""

import ast
import operator
import re

__all__ = ["calculator"]

_OP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _eval(node: ast.AST) -> float | int:
    """递归求值 AST 节点，仅支持常量和基本算术运算"""
    if isinstance(node, ast.Constant):
        return node.n
    elif isinstance(node, ast.BinOp):
        return _OP_MAP[type(node.op)](_eval(node.left), _eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        return _OP_MAP[type(node.op)](_eval(node.operand))
    else:
        raise TypeError(f"Unsupported node type: {type(node)}")


def calculator(expression: str) -> str:
    """计算器工具，支持加减乘除幂运算

    Args:
        expression: 数学表达式字符串，例如 "2 + 3 * 4"
    Returns:
        计算结果字符串
    """
    try:
        cleaned = re.sub(r'[^0-9+\-*/().\s]', '', expression)
        tree = ast.parse(cleaned, mode='eval')
        result = _eval(tree.body)
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return str(result)
    except Exception as e:
        return f"计算错误: {str(e)}"
