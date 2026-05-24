import json
import os
import random
import re
import urllib.parse
from skill import BaseSkill

MUSIC_DIR = r"F:\音乐"

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".wma", ".m4a", ".ogg", ".aac", ".ape", ".opus"}


def _scan_music():
    if not os.path.exists(MUSIC_DIR):
        return []
    files = []
    for root, _, filenames in os.walk(MUSIC_DIR):
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                files.append(os.path.join(root, f))
    return files


def play_random_music():
    files = _scan_music()
    if not files:
        return "❌ F:\\音乐 目录下没有找到音乐文件"
    chosen = random.choice(files)
    name = os.path.basename(chosen)
    url = "/api/music/play?path=" + urllib.parse.quote(chosen)
    return f"▶️ 正在播放：{name}\n[AUDIO]{url}[/AUDIO]"


def stop_music():
    return "⏹️ 音乐已停止\n[AUDIO_STOP]"


def get_tools_prompt():
    return (
        "\n\n【工具 - 音乐播放】\n"
        "当用户说播放音乐、放歌、听歌、来点音乐等时，使用 play_music 从 F:\\音乐 随机播放一首。\n"
        "当用户说关闭音乐、停止播放、别放了等时，使用 stop_music 停止当前播放。\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"play_music","params":{}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"stop_music","params":{}}[/TOOL_CALL]\n'
    )


class MusicSkill(BaseSkill):
    name = "音乐播放"
    description = "从 F:\\音乐 随机选择并播放音乐文件"
    triggers = ["播放音乐", "放歌", "听歌", "来点音乐", "放音乐", "随机播放", "关闭音乐", "停止播放", "别放了"]

    async def execute(self, message, context=None):
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                if tool == "play_music":
                    return play_random_music()
                if tool == "stop_music":
                    return stop_music()
            except json.JSONDecodeError:
                pass

        for t in self.triggers:
            if t in message.lower():
                if t in ("关闭音乐", "停止播放", "别放了"):
                    return stop_music()
                return play_random_music()

        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
