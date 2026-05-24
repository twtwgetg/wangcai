import json
import os
import re
import asyncio
from skill import BaseSkill
from relay_client import get_relay, ensure_connected
from config import get_relay_config

_relay_tools_cache = None
_last_tools_fetch = 0


def get_tools_prompt():
    cfg = get_relay_config()
    if not cfg.get("enabled"):
        return ""
    return (
        "\n\n【工具 - 远程代理】\n"
        "当用户需要操作远程服务器上的资源（如查找远程文件、播放远程音乐等）时使用。\n"
        "可用远程工具通过 relay_list_tools 获取。\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"relay_list_tools","params":{}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"relay_exec","params":{"tool":"工具名","params":{"参数名":"值"}}}[/TOOL_CALL]\n'
    )


async def relay_list_tools():
    cfg = get_relay_config()
    if not cfg.get("enabled"):
        return "❌ 远程代理未启用（config.json relay.enabled = false）"
    ok = await ensure_connected()
    if not ok:
        return "❌ 无法连接到远程服务器"
    result = await get_relay().send_request("list_tools", {}, timeout=15)
    if "error" in result:
        return f"❌ {result['error']}"
    tools = result.get("data", [])
    if not tools:
        return "远程代理上暂无可用工具"
    lines = ["📦 远程代理可用工具：\n"]
    for t in tools:
        lines.append(f"  • {t['name']}: {t['description']}")
    return "\n".join(lines)


async def relay_exec(tool, params=None):
    cfg = get_relay_config()
    if not cfg.get("enabled"):
        return "❌ 远程代理未启用"
    ok = await ensure_connected()
    if not ok:
        return "❌ 无法连接到远程服务器"
    if params is None:
        params = {}
    result = await get_relay().send_request(tool, params, timeout=120)
    if "error" in result:
        return f"❌ 远程执行失败：{result['error']}"
    return result.get("data", str(result))


class RelaySkill(BaseSkill):
    name = "远程代理"
    description = "通过远程服务器连接到云端代理，执行文件查找、音乐播放等操作"
    triggers = ["远程", "云服务器", "云端", "remote", "relay"]

    async def execute(self, message, context=None):
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                params = data.get("params", {})
                if tool == "relay_list_tools":
                    return await relay_list_tools()
                if tool == "relay_exec":
                    return await relay_exec(params.get("tool"), params.get("params"))
            except json.JSONDecodeError:
                pass
            except Exception as e:
                return f"❌ 远程代理执行失败：{e}"
        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
