import difflib
import json
import os
import random
import re
import urllib.parse
from skill import BaseSkill

MOVIE_DIR = r"F:\电影"

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".wmv", ".flv", ".mov", ".m4v", ".webm"}


def _scan_movies():
    if not os.path.exists(MOVIE_DIR):
        return []
    files = []
    for root, _, filenames in os.walk(MOVIE_DIR):
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                files.append(os.path.join(root, f))
    return files


def _find_by_name(query):
    files = _scan_movies()
    if not files:
        return None
    query_lower = query.lower().replace(" ", "")
    # exact match
    for f in files:
        name_stem = os.path.splitext(os.path.basename(f))[0].lower().replace(" ", "")
        if query_lower == name_stem:
            return f
    # substring match
    for f in files:
        name_stem = os.path.splitext(os.path.basename(f))[0].lower().replace(" ", "")
        if query_lower in name_stem or name_stem in query_lower:
            return f
    # fuzzy match on basename
    names = {f: os.path.splitext(os.path.basename(f))[0] for f in files}
    matches = difflib.get_close_matches(query, list(names.values()), n=1, cutoff=0.4)
    if matches:
        for f, n in names.items():
            if n == matches[0]:
                return f
    return None


def play_movie(name=""):
    files = _scan_movies()
    if not files:
        return "❌ F:\\电影 目录下没有找到视频文件"
    if name:
        matched = _find_by_name(name)
        if matched:
            chosen = matched
        else:
            return f"❌ 未找到与「{name}」相关的视频"
    else:
        chosen = random.choice(files)
    name_str = os.path.basename(chosen)
    url = "/api/video/play?path=" + urllib.parse.quote(chosen)
    return f"🎬 正在播放：{name_str}\n[VIDEO]{url}[/VIDEO]"


def list_movies():
    files = _scan_movies()
    if not files:
        return "❌ F:\\电影 目录下没有找到视频文件"
    lines = [f"📂 F:\\电影 下找到 {len(files)} 个视频：\n"]
    for f in sorted(files):
        size = os.path.getsize(f)
        size_str = f"{size / 1024 / 1024:.0f}MB" if size > 1024 * 1024 else f"{size / 1024:.0f}KB"
        lines.append(f"  • {os.path.basename(f)} ({size_str})")
    return "\n".join(lines)


def stop_video():
    return "⏹️ 视频已关闭\n[VIDEO_STOP]"


def get_tools_prompt():
    return (
        "\n\n【工具 - 电影播放】\n"
        "当用户说播放电影、看电影、放视频、放电影等时，使用 play_movie 从 F:\\电影 播放一部。\n"
        "  如果用户指定了影片名称，将 name 参数设为影片名（如「生化危机」），会自动查找最接近的影片。\n"
        "  如果用户没有指定名称，name 留空，随机播放一部。\n"
        "使用 list_movies 列出所有视频文件。\n"
        "当用户说关闭视频、停止播放、关闭电影、暂停等时，使用 stop_video 关闭页面中的视频。\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"play_movie","params":{"name":"生化危机"}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"play_movie","params":{}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"list_movies","params":{}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"stop_video","params":{}}[/TOOL_CALL]\n'
    )


class MovieSkill(BaseSkill):
    name = "电影播放"
    description = "从 F:\\电影 播放视频文件，支持按名称查找"
    triggers = ["播放电影", "看电影", "放视频", "放电影", "播放视频", "关闭视频", "停止播放", "关闭电影"]

    async def execute(self, message, context=None):
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                if tool == "play_movie":
                    params = data.get("params", {})
                    return play_movie(params.get("name", ""))
                if tool == "list_movies":
                    return list_movies()
                if tool == "stop_video":
                    return stop_video()
            except json.JSONDecodeError:
                pass

        for t in self.triggers:
            if t in message.lower():
                if t in ("关闭视频", "停止播放", "关闭电影"):
                    return stop_video()
                return play_movie("")

        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
