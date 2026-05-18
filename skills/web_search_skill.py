import json
import re
import requests
from skill import BaseSkill

SEARXNG_URL = "http://localhost:9528/search"


def search_web(query, max_results=5):
    try:
        resp = requests.get(
            SEARXNG_URL,
            params={"q": query, "format": "json", "language": "zh-CN"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])[:max_results]
        if not results:
            return f"未搜索到「{query}」的相关结果"

        lines = [f"🔍 搜索「{query}」的结果：\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            snippet = r.get("content", "") or ""
            lines.append(f"{i}. {title}")
            lines.append(f"   {snippet}")
            lines.append(f"   {url}")
            lines.append("")
        return "\n".join(lines)

    except requests.exceptions.ConnectionError:
        return f"❌ 无法连接到搜索引擎 ({SEARXNG_URL})，请确认 SearXNG 服务是否已启动"
    except Exception as e:
        return f"❌ 搜索失败：{e}"


def search_images(query, max_results=5):
    try:
        resp = requests.get(
            SEARXNG_URL,
            params={
                "q": query,
                "format": "json",
                "categories": "images",
                "language": "zh-CN",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])[:max_results]
        if not results:
            return f"未搜索到「{query}」的图片"

        lines = [f"🖼️ 搜索「{query}」的图片结果：\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            img_src = r.get("img_src", "") or r.get("thumbnail_src", "")
            resolution = r.get("resolution", "")
            lines.append(f"{i}. {title}")
            if resolution:
                lines.append(f"   尺寸：{resolution}")
            lines.append(f"   链接：{url}")
            if img_src:
                lines.append(f"   [IMG]{img_src}[/IMG]")
            lines.append("")
        return "\n".join(lines)

    except requests.exceptions.ConnectionError:
        return f"❌ 无法连接到搜索引擎 ({SEARXNG_URL})，请确认 SearXNG 服务是否已启动"
    except Exception as e:
        return f"❌ 搜索图片失败：{e}"


def get_tools_prompt():
    return (
        "\n\n【工具 - 网络搜索】\n"
        "当你需要实时信息、最新新闻、天气、百科知识等，或用户明确要求上网搜索时，"
        "使用以下格式调用搜索工具。注意：不需要搜索的问题不要调用。\n\n"
        "可用工具：\n"
        "1. web_search - 通用网页搜索\n"
        '   调用格式：[TOOL_CALL]{"tool":"web_search","params":{"q":"搜索关键词"}}[/TOOL_CALL]\n'
        "   示例：\n"
        '     用户：今天青岛天气怎么样？\n'
        '     你：[TOOL_CALL]{"tool":"web_search","params":{"q":"青岛天气 今天"}}[/TOOL_CALL]\n\n'
        "2. web_search_image - 搜索图片\n"
        '   调用格式：[TOOL_CALL]{"tool":"web_search_image","params":{"q":"搜索关键词"}}[/TOOL_CALL]\n'
        "   当用户查找图片、照片、壁纸等时使用此工具。\n"
        "   示例：\n"
        '     用户：找一些猫的图片\n'
        '     你：[TOOL_CALL]{"tool":"web_search_image","params":{"q":"猫"}}[/TOOL_CALL]\n\n'
        "注意：一次搜索只做一件事，不要同时搜索多个关键词。\n"
    )


def parse_search_intent(message):
    m = re.search(r'(?:搜索|搜一下|搜搜|查一下|查查|查找|查询|上网|百度|谷歌)\s*(.+?)(?:$|的信息|的情况|的资料|的内容)', message)
    if m:
        return m.group(1).strip()
    m = re.search(r'[，,]\s*(.+?)(?:怎么[样样]|是什么|在哪里|多少钱|如何)', message)
    if m:
        return m.group(1).strip()
    return None


class WebSearchSkill(BaseSkill):
    name = "网络搜索"
    description = "通过 SearXNG 搜索引擎搜索网络上的实时信息和图片"
    triggers = ["搜索", "搜一下", "搜搜", "查一下", "查查", "查找", "上网查", "上网搜", "百度一下"]

    async def execute(self, message, context=None):
        match = re.search(r'\[TOOL_CALL\](.*?)\[/TOOL_CALL\]', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                q = data.get("params", {}).get("q", "")
                if not q:
                    return None
                tool = data.get("tool")
                if tool == "web_search":
                    return search_web(q)
                if tool == "web_search_image":
                    return search_images(q)
            except json.JSONDecodeError:
                pass

        query = parse_search_intent(message)
        if not query:
            return None

        is_image = bool(re.search(r'图片|照片|壁纸|截图|插画|插图|头像|背景|封面|海报|相片|图集|图案', query))
        return search_images(query) if is_image else search_web(query)

    def get_tools_prompt(self):
        return get_tools_prompt()
