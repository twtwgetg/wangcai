import re
from skill import BaseSkill


class CalculatorSkill(BaseSkill):
    name = "计算器"
    description = "计算数学表达式"
    triggers = ["计算", "等于", "多少"]

    async def execute(self, message, context=None):
        patterns = [
            r"计算\s*([\d\+\-\*\/\(\)\s\.]+)",
            r"([\d\+\-\*\/\(\)\s\.]+)\s*等于多少",
            r"([\d\+\-\*\/\(\)\s\.]+)\s*=\s*\?",
        ]
        for pat in patterns:
            m = re.search(pat, message)
            if m:
                expr = m.group(1).strip()
                try:
                    result = eval(expr, {"__builtins__": {}}, {})
                    return f"{expr} = {result}"
                except Exception as e:
                    return f"计算错误：{e}"
        return None
