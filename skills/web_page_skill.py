import os
import re
import json
import httpx
from skill import BaseSkill
from config import get_llm_config

GENERATED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "generated")
BASE_URL = "http://localhost:9527/static/generated/"

GENERATE_PROMPT = """You are a professional frontend developer. Generate a complete, self-contained HTML page based on the user's request.

Requirements:
- ALL code in one HTML file (inline CSS and JS)
- Modern, clean UI design
- Chinese language interface
- For games: ensure they are fully playable with keyboard/mouse/touch
- Code must be complete and working
- Include appropriate styling, animations, and interactivity

User request: {description}

Output ONLY the HTML code, no explanations."""


def page_list():
    if not os.path.exists(GENERATED_DIR):
        return "📂 尚未生成任何页面"
    files = sorted(os.listdir(GENERATED_DIR))
    if not files:
        return "📂 尚未生成任何页面"
    lines = [f"📂 已生成 {len(files)} 个页面：\n"]
    for f in files:
        lines.append(f"  • {f} → {BASE_URL}{f}")
    return "\n".join(lines)


def open_page(filename):
    filepath = os.path.join(GENERATED_DIR, filename)
    if not os.path.exists(filepath):
        files = os.listdir(GENERATED_DIR)
        matches = [f for f in files if filename.lower() in f.lower()]
        if not matches:
            return f"❌ 未找到匹配的文件：{filename}"
        filepath = os.path.join(GENERATED_DIR, matches[0])
        filename = matches[0]
    os.startfile(filepath)
    return f"✅ 已打开：{filename}"


def generate_page(description, filename=None):
    os.makedirs(GENERATED_DIR, exist_ok=True)
    if not filename:
        safe = re.sub(r'[^\w\u4e00-\u9fff]+', '_', description)[:30]
        safe = safe.strip("_")
        filename = f"{safe}.html" if safe else f"page_{len(os.listdir(GENERATED_DIR)) + 1}.html"
    if not filename.endswith(".html"):
        filename += ".html"

    llm_config = get_llm_config()
    api_url = llm_config.get("api_url", "https://api.deepseek.com/v1")
    model = llm_config.get("model_name", "deepseek-chat")
    api_key = llm_config.get("api_key", "")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    prompt = GENERATE_PROMPT.format(description=description)

    response = httpx.post(
        f"{api_url}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 4096,
        },
        timeout=120.0,
    )
    data = response.json()
    html_code = data["choices"][0]["message"]["content"]

    code_match = re.search(r'```html\s*\n(.*?)\n```', html_code, re.DOTALL)
    if code_match:
        html_code = code_match.group(1)

    filepath = os.path.join(GENERATED_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_code)

    return f"✅ 页面已生成：{filename}\n📁 {filepath}\n🔗 {BASE_URL}{filename}"


def get_tools_prompt():
    return (
        "\n\n【工具 - 页面/游戏生成】\n"
        "当用户说生成网页、做个页面、做个游戏、写个页面、创建一个页面等时：\n"
        '1. 调用 generate_page，传入 description（用户的详细需求）和可选的 filename\n'
        "2. 如果想查看已生成的页面列表，调用 page_list\n"
        "3. 如果想在浏览器中打开页面，调用 open_page 传入 filename\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"generate_page","params":{"description":"用户的需求描述"}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"page_list","params":{}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"open_page","params":{"filename":"xxx.html"}}[/TOOL_CALL]\n'
    )


PAGE_TOOLS = {
    "generate_page": {
        "fn": generate_page,
        "description": "根据用户需求使用AI生成一个完整的HTML页面（支持网页、小游戏、工具等），保存到public/generated目录",
        "params": {"description": "用户对页面的详细需求描述", "filename": "保存的文件名（可选，不填自动生成）"},
    },
    "page_list": {
        "fn": page_list,
        "description": "列出已生成的所有HTML页面",
        "params": {},
    },
    "open_page": {
        "fn": open_page,
        "description": "在浏览器中打开已生成的页面",
        "params": {"filename": "文件名（支持模糊匹配）"},
    },
}


class WebPageSkill(BaseSkill):
    name = "页面生成"
    description = "根据用户需求生成HTML页面或游戏"
    triggers = ["生成页面", "生成游戏", "做个网页", "做个游戏", "写个页面", "创建一个页面"]

    async def execute(self, message, context=None):
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                params = data.get("params", {})
                if tool in PAGE_TOOLS:
                    return PAGE_TOOLS[tool]["fn"](**params)
            except json.JSONDecodeError:
                pass
            except Exception as e:
                return f"❌ 执行失败：{e}"
        for t in self.triggers:
            if t in message:
                return generate_page(message)
        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
