import os
import json
import re
import shutil
import time
from datetime import datetime
from skill import BaseSkill


def _fmt_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} PB"


def _fmt_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def create_folder(path):
    os.makedirs(path, exist_ok=True)
    return f"✅ 已创建文件夹：{path}"


def create_file(path, content=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ 已创建文件：{path}"


def list_dir(path):
    if not os.path.exists(path):
        return f"❌ 路径不存在：{path}"
    items = os.listdir(path)
    folders = []
    files = []
    for name in sorted(items):
        full = os.path.join(path, name)
        try:
            stat = os.stat(full)
            if os.path.isdir(full):
                folders.append((name, stat))
            else:
                files.append((name, stat))
        except OSError:
            if os.path.isdir(full):
                folders.append((name, None))
            else:
                files.append((name, None))

    lines = []
    lines.append(f"╔══ 📂 {path} 文件列表 ══╗")
    lines.append(f"║  文件夹: {len(folders)} 个    文件: {len(files)} 个")
    lines.append("╠═══════════════════════════════════════════╣")

    if folders:
        lines.append("║  📁 文件夹:")
        for name, stat in folders:
            if stat:
                date = _fmt_time(stat.st_mtime)
                lines.append(f"║    📁 {name:{30}}  {date}")
            else:
                lines.append(f"║    📁 {name}")
        lines.append("╠═══════════════════════════════════════════╣")

    if files:
        lines.append("║  📄 文件:")
        for name, stat in files:
            if stat:
                size = _fmt_size(stat.st_size)
                date = _fmt_time(stat.st_mtime)
                lines.append(f"║    📄 {name:{28}}  {size:>8}  {date}")
            else:
                lines.append(f"║    📄 {name}")
        lines.append("╠═══════════════════════════════════════════╣")

    if not folders and not files:
        lines.append("║  （空目录）")
        lines.append("╠═══════════════════════════════════════════╣")

    lines.append(f"╚══ 共 {len(folders) + len(files)} 项 ══╝")
    return "\n".join(lines)


def delete_file(path):
    if os.path.isfile(path):
        os.remove(path)
        return f"✅ 已删除文件：{path}"
    return f"❌ 文件不存在：{path}"


def _rmtree_handler(func, path, exc_info):
    try:
        os.chmod(path, 0o777)
        func(path)
    except Exception as e2:
        raise OSError(f"无法删除 {path}：{e2}")


def delete_folder(path):
    if not os.path.isdir(path):
        return f"❌ 目录不存在：{path}"
    try:
        os.rmdir(path)
    except OSError:
        try:
            shutil.rmtree(path, onerror=_rmtree_handler)
        except Exception as e:
            return f"❌ 删除失败：{e}"
    if os.path.isdir(path):
        return f"❌ 删除后目录仍然存在（可能被重建或权限不足）：{path}"
    return f"✅ 已删除目录：{path}"


def find_empty_dirs(path, max_depth=5):
    """递归查找指定路径下的空文件夹"""
    if not os.path.exists(path):
        return f"❌ 路径不存在：{path}"
    if not os.path.isdir(path):
        return f"❌ 不是目录：{path}"

    empty_list = []

    def scan(current, depth):
        if depth > max_depth:
            return
        try:
            items = os.listdir(current)
            if not items:
                empty_list.append(current)
                return
            for item in items:
                full = os.path.join(current, item)
                if os.path.isdir(full):
                    scan(full, depth + 1)
        except PermissionError:
            pass
        except OSError:
            pass

    scan(path, 0)

    if not empty_list:
        return f"在 {path} 下未找到空文件夹（扫描深度 {max_depth} 层）"

    lines = [f"📂 在 {path} 下找到 {len(empty_list)} 个空文件夹：\n"]
    for d in sorted(empty_list):
        lines.append(f"  📁 {d}")
    lines.append(f"\n共 {len(empty_list)} 个空文件夹")
    return "\n".join(lines)


FILE_TOOLS = {
    "create_folder": {
        "fn": create_folder,
        "description": "创建文件夹",
        "params": {"path": "文件夹路径（如 E:/test）"},
    },
    "create_file": {
        "fn": create_file,
        "description": "创建文件",
        "params": {"path": "文件路径（如 E:/test/hello.txt）", "content": "文件内容（可选）"},
    },
    "list_dir": {
        "fn": list_dir,
        "description": "列出目录下的文件和子目录",
        "params": {"path": "目录路径"},
    },
    "find_empty_dirs": {
        "fn": find_empty_dirs,
        "description": "递归查找指定路径下的所有空文件夹",
        "params": {"path": "要扫描的目录路径（如 F:/）"},
    },
    "delete_file": {
        "fn": delete_file,
        "description": "删除文件",
        "params": {"path": "文件路径"},
    },
    "delete_folder": {
        "fn": delete_folder,
        "description": "删除目录（空目录用os.rmdir，非空目录自动递归删除）",
        "params": {"path": "目录路径"},
    },
}


def get_tools_prompt():
    lines = [
        "\n\n【重要】你可以执行以下真实操作，当用户提出相关请求时，你必须使用工具来完成，不能说自己做不到：",
        "调用格式（必须严格按此格式，不要加任何多余文字在这一行里）：",
        '[TOOL_CALL]{"tool":"工具名","params":{"参数名":"值"}}[/TOOL_CALL]',
        "",
        "可用工具：",
    ]
    for name, info in FILE_TOOLS.items():
        params_str = ", ".join(f"{k}: {v}" for k, v in info["params"].items())
        lines.append(f"  • {name}: {info['description']}, 参数: {params_str}")
    lines.extend([
        "",
        "示例：",
        '  用户：在E盘创建个文件夹叫test',
        '  你：[TOOL_CALL]{"tool":"create_folder","params":{"path":"E:/test"}}[/TOOL_CALL]',
        '',
        '  用户：把我C盘根目录列一下',
        '  你：[TOOL_CALL]{"tool":"list_dir","params":{"path":"C:/"}}[/TOOL_CALL]',
        '',
        '  用户：看下F盘哪些文件夹是空的',
        '  你：[TOOL_CALL]{"tool":"find_empty_dirs","params":{"path":"F:/"}}[/TOOL_CALL]',
        '',
        "重要规则：每次只调用一个工具，收到结果后直接回复用户，不要再调用第二个工具。",
    ])
    return "\n".join(lines)


def execute_file_tool(tool_name, params):
    tool = FILE_TOOLS.get(tool_name)
    if tool:
        try:
            return tool["fn"](**params)
        except Exception as e:
            return f"❌ 执行失败：{e}"
    return f"❌ 未知工具：{tool_name}"


def parse_file_intent(message):
    """直接解析用户意图，作为 LLM 不调用工具的兜底"""
    m = re.search(r'(?:创建|新建|建)(?:一个)?(?:文件夹|目录)\s*[叫称]?\s*(\S+)', message)
    if m:
        name = m.group(1).strip().rstrip("的")
        drive_match = re.search(r'([A-Za-z]):?[\\/]', message)
        if drive_match:
            path = f"{drive_match.group(1).upper()}:/{name}"
        else:
            path = name
        return "create_folder", {"path": path}

    has_list_cmd = re.search(r'列|列出|显示|展示', message)
    if has_list_cmd:
        drive_match = re.search(r'([A-Za-z])\s*盘', message)
        if not drive_match:
            drive_match = re.search(r'([A-Za-z]):', message)
        if drive_match:
            path = f"{drive_match.group(1).upper()}:/"
            return "list_dir", {"path": path}
        path_match = re.search(r'列(?:出)?\s*(.*?)(?:目录|文件夹|内容|$)|\b(?:目录|文件夹|路径)\s*(.*?)\s*列', message)
        if path_match:
            p = path_match.group(1) or path_match.group(2) or "."
            return "list_dir", {"path": p.strip()}
        return "list_dir", {"path": "."}

    return None, None


class FileOpsSkill(BaseSkill):
    name = "文件操作"
    description = "创建/删除文件或文件夹、列出目录内容"
    triggers = ["创建文件夹", "创建目录", "列出", "列一下", "文件夹列", "目录列", "列目录", "盘根目录", "文件列表", "列表"]

    async def execute(self, message, context=None):
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool_name = data.get("tool", "")
                if tool_name in FILE_TOOLS:
                    return execute_file_tool(tool_name, data.get("params", {}))
                return None
            except json.JSONDecodeError as e:
                return f"❌ 工具调用格式错误：{e}"

        tool_name, params = parse_file_intent(message)
        if tool_name and params:
            return execute_file_tool(tool_name, params)

        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
