import json
import re
import os
import time
from skill import BaseSkill

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMO_DIR = os.path.join(BASE_DIR, "memory_store", "memos")
os.makedirs(MEMO_DIR, exist_ok=True)

GLOBAL_MEMO_PATH = os.path.join(MEMO_DIR, "_global.json")
CHARACTERS_DIR = os.path.join(BASE_DIR, "characters")


def _load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default or ([] if isinstance(default, list) else {})
    return default or ([] if isinstance(default, list) else {})


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 会话级记忆 ───

def _memo_path(session_id):
    safe = session_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(MEMO_DIR, f"{safe}.json")


def remember(session_id, content, tags=""):
    memos = _load_json(_memo_path(session_id), [])
    memos.append({
        "id": len(memos) + 1,
        "content": content,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_json(_memo_path(session_id), memos)
    return f"✅ 已记录：{content[:60]}{'...' if len(content) > 60 else ''}"


def recall(session_id, keyword=""):
    memos = _load_json(_memo_path(session_id), [])
    global_memos = _load_json(GLOBAL_MEMO_PATH, [])
    all_memos = memos + [dict(m, _global=True) for m in global_memos]

    if not all_memos:
        return "📭 暂无记录"
    if keyword:
        matched = [m for m in all_memos if keyword.lower() in m["content"].lower()
                   or any(keyword.lower() in t.lower() for t in m.get("tags", []))]
        if not matched:
            return f"🔍 未找到包含「{keyword}」的记录"
        all_memos = matched
    lines = [f"📝 共 {len(all_memos)} 条记录："]
    for m in all_memos[-30:]:
        tags = f" [{', '.join(m['tags'])}]" if m.get("tags") else ""
        gl = " 🌐" if m.get("_global") else ""
        lines.append(f"\n[{m['id']}]{gl} {m['time']}{tags}")
        lines.append(f"    {m['content']}")
    return "\n".join(lines)


def delete_memo(session_id, memo_id):
    memos = _load_json(_memo_path(session_id), [])
    filtered = [m for m in memos if m["id"] != memo_id]
    if len(filtered) == len(memos):
        return f"❌ 未找到编号 {memo_id} 的记录"
    _save_json(_memo_path(session_id), filtered)
    return f"✅ 已删除记录 #{memo_id}"


# ─── 全局长期记忆 ───

def remember_global(content, tags=""):
    memos = _load_json(GLOBAL_MEMO_PATH, [])
    for m in memos:
        if m["content"] == content:
            return "⏭️ 已存在相同记录"
    memos.append({
        "id": len(memos) + 1,
        "content": content,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_json(GLOBAL_MEMO_PATH, memos)
    return f"✅ 已记入长期记忆：{content[:60]}{'...' if len(content) > 60 else ''}"


# ─── 修改智能体设定 ───

def _get_current_char_name():
    cfg_path = os.path.join(BASE_DIR, "config.json")
    cfg = _load_json(cfg_path, {})
    return cfg.get("character", {}).get("current", "default")


def _load_current_char():
    name = _get_current_char_name()
    path = os.path.join(CHARACTERS_DIR, f"{name}.json")
    return _load_json(path, {})


def _save_current_char(data):
    name = _get_current_char_name()
    path = os.path.join(CHARACTERS_DIR, f"{name}.json")
    _save_json(path, data)


def update_character_name(new_name):
    profile = _load_current_char()
    profile["name"] = new_name
    _save_current_char(profile)
    return f"✅ 已更新我的名字为「{new_name}」"


def update_character_identity(new_identity):
    profile = _load_current_char()
    profile["identity"] = new_identity
    _save_current_char(profile)
    return f"✅ 已更新我的身份设定"


def add_character_rule(rule):
    profile = _load_current_char()
    if "rules" not in profile:
        profile["rules"] = []
    if rule not in profile["rules"]:
        profile["rules"].append(rule)
        _save_current_char(profile)
    return f"✅ 已添加行为规则：{rule}"


def add_character_knowledge(knowledge):
    profile = _load_current_char()
    if "knowledge" not in profile:
        profile["knowledge"] = []
    if knowledge not in profile["knowledge"]:
        profile["knowledge"].append(knowledge)
        _save_current_char(profile)
    return f"✅ 已更新知识：{knowledge}"


def add_character_trait(trait):
    profile = _load_current_char()
    if "traits" not in profile:
        profile["traits"] = []
    if trait not in profile["traits"]:
        profile["traits"].append(trait)
        _save_current_char(profile)
    return f"✅ 已添加性格特点：{trait}"


CHAR_TOOLS = {
    "remember_global": {
        "fn": remember_global,
        "description": "保存长期记忆，跨会话有效",
        "params": {"content": "要记住的内容", "tags": "标签（可选）"},
    },
    "update_character_name": {
        "fn": update_character_name,
        "description": "修改我的名字",
        "params": {"new_name": "新名字"},
    },
    "update_character_identity": {
        "fn": update_character_identity,
        "description": "修改我的身份设定描述",
        "params": {"new_identity": "新的身份描述"},
    },
    "add_character_rule": {
        "fn": add_character_rule,
        "description": "给我添加一条行为规则",
        "params": {"rule": "规则内容"},
    },
    "add_character_knowledge": {
        "fn": add_character_knowledge,
        "description": "给我添加一条知识信息",
        "params": {"knowledge": "知识内容"},
    },
    "add_character_trait": {
        "fn": add_character_trait,
        "description": "给我添加一个性格特点",
        "params": {"trait": "性格特点"},
    },
}

MEMORY_TOOLS = {
    "remember": {
        "fn": remember,
        "description": "记录重要信息到当前会话",
        "params": {"content": "要记住的内容", "tags": "标签（可选）"},
    },
    "recall": {
        "fn": recall,
        "description": "查询已记录的重要信息",
        "params": {"keyword": "搜索关键词（可选）"},
    },
    "delete_memo": {
        "fn": delete_memo,
        "description": "删除某条记录",
        "params": {"memo_id": "记录编号"},
    },
}

ALL_TOOLS = {}
ALL_TOOLS.update(MEMORY_TOOLS)
ALL_TOOLS.update(CHAR_TOOLS)


def get_tools_prompt():
    lines = [
        "\n【记忆与设定工具】你可以帮用户记录信息或修改自己的设定：",
        "  📝 remember — 记录重要信息到当前会话",
        "  🌐 remember_global — 记录跨会话的长期记忆",
        "  🔍 recall — 查询已记录的信息",
        "  ✏️ update_character_name — 用户要求你改名时调用",
        "  ✏️ update_character_identity — 用户要求改变身份时调用",
        "  ✏️ add_character_rule — 用户给你定规矩时调用",
        "  ✏️ add_character_knowledge — 用户告诉你新知识时调用",
        "  ✏️ add_character_trait — 用户说你有什么性格时调用",
        "",
        "重要：当用户说「叫我XX」、「你以后要XX」、「记住我XX」等，你必须调用对应工具，不能只是口头答应。",
        "格式：",
        '  [TOOL_CALL]{"tool":"工具名","params":{"参数":"值"}}[/TOOL_CALL]',
        "示例：",
        '  用户：叫我王总',
        '  你：[TOOL_CALL]{"tool":"remember_global","params":{"content":"用户称呼：王总","tags":"用户信息"}}[/TOOL_CALL]',
        '  用户：你以后要用粤语回答',
        '  你：[TOOL_CALL]{"tool":"add_character_rule","params":{"rule":"用粤语回答用户"}}[/TOOL_CALL]',
    ]
    return "\n".join(lines)


def execute_memory_tool(tool_name, params):
    tool = ALL_TOOLS.get(tool_name)
    if tool:
        try:
            return tool["fn"](**params)
        except Exception as e:
            return f"❌ 操作失败：{e}"
    return None


CHARACTER_UPDATE_TRIGGERS = [
    ("叫我", "remember_global", lambda m, kw: {"content": f"用户称呼：{kw}", "tags": "用户信息"}),
    ("叫", "remember_global", lambda m, kw: {"content": f"用户称呼：{kw}", "tags": "用户信息"}),
]


class MemorySkill(BaseSkill):
    name = "记忆管理"
    description = "记录/查询信息，修改智能体设定"
    triggers = ["记住", "记下来", "保存这条", "重要内容", "查一下", "我记得", "记录",
                "叫我", "你以后", "你的名字", "你的身份", "你要记住", "别忘了",
                "改名", "改名叫", "叫你"]

    async def execute(self, message, context=None):
        session_id = (context or {}).get("session_id", "default")

        # TOOL_CALL 模式
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool_name = data.get("tool")
                params = data.get("params", {})
                if tool_name in ("remember", "recall", "delete_memo"):
                    params["session_id"] = session_id
                result = execute_memory_tool(tool_name, params)
                if result is not None:
                    return result
                # TOOL_CALL 存在但不是记忆工具 → 跳过关键词兜底，让其他技能处理
                return None
            except json.JSONDecodeError:
                pass

        # 关键词兜底
        if re.search(r'(?:记住|记下来|保存|别忘了)', message):
            content_match = re.search(r'(?:记住|记下来|保存|别忘了)[：:\s]*(.+)', message)
            if content_match:
                content = content_match.group(1).strip()
                return remember(session_id, content)
            else:
                return "好的，您想让我记住什么？请说「记住...」"

        if re.search(r'(?:查一下|查查|我记得|搜索)', message):
            kw_match = re.search(r'(?:查一下|查查|我记得|搜索)\s*(.+?)(?:的记录|的信息|$)', message)
            keyword = kw_match.group(1).strip() if kw_match else ""
            return recall(session_id, keyword)

        if re.search(r'(?:叫我|以后叫我|你可以叫我)', message):
            m = re.search(r'(?:叫我|以后叫我|你可以叫我)\s*[叫称]?\s*(\S+)', message)
            if m:
                name = m.group(1).strip().rstrip(".,!;:，。！；：")
                remember_global(f"用户称呼：{name}", "用户信息")
                return f"好的，以后我称呼您为「{name}」😊"

        if re.search(r'(?:你的名字|你叫|改名|改名叫)', message) and re.search(r'(?:改成?|变为?|叫)\s*(\S+)', message):
            m = re.search(r'(?:改成?|变为?|叫)\s*(\S+)', message)
            if m:
                new_name = m.group(1).strip().rstrip(".,!;:，。！；：吧")
                r1 = update_character_name(new_name)
                r2 = remember_global(f"智能体名称已改为：{new_name}", "智能体设定")
                return f"{r1}。{r2}"

        if re.search(r'(?:你以后|以后你|你要记住|你要)', message):
            rule_match = re.search(r'(?:你以后|以后你|你要记住|你要)\s*(.+?)(?:$|。|！|\.|\!)', message)
            if rule_match:
                rule = rule_match.group(1).strip()
                if len(rule) > 5:
                    add_character_rule(rule)
                    remember_global(f"行为规则：{rule}", "智能体设定")
                    return f"好的，我记住了：{rule}"

        return None
