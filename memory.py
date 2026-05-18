import json
import os
from config import get_memory_config

MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_store")


def _ensure_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _session_path(session_id):
    _ensure_dir()
    safe_name = session_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(MEMORY_DIR, f"{safe_name}.json")


def count_tokens(text):
    if not text:
        return 0
    tokens = 0
    for char in text:
        if ord(char) > 127:
            tokens += 2
        elif char.isalpha():
            tokens += 1
        else:
            tokens += 1
    return tokens


def estimate_messages_tokens(messages):
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", ""))
        total += count_tokens(msg.get("role", ""))
    return total


def compress_messages(messages, max_tokens):
    if estimate_messages_tokens(messages) <= max_tokens:
        return messages
    keep_recent = get_memory_config().get("keep_recent_messages", 6)
    if keep_recent > len(messages):
        keep_recent = len(messages)
    recent = messages[-keep_recent:]
    older = messages[:-keep_recent]
    summary_text = ""
    for msg in older:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")
        summary_text += f"[{role}]: {content}\n"
    compressed = []
    if summary_text:
        compressed.append({
            "role": "system",
            "content": f"[历史对话摘要]\n{summary_text.strip()}"
        })
    compressed.extend(recent)
    if estimate_messages_tokens(compressed) > max_tokens and len(compressed) > 2:
        return compress_messages(compressed, max_tokens)
    return compressed


AUTO_SUMMARIZE_PROMPT = """从对话中提取需要记住的重要信息：
1. 用户个人信息（名字、年龄、职业、联系方式、地址等）
2. 用户的偏好和习惯（喜欢什么、不喜欢什么）
3. 重要的约定、承诺、待办事项
4. 正在进行的任务和进度
5. 项目相关的关键决策和细节

以简洁要点输出，每行一个。如果没有重要信息，回复"无"。"""


def build_summarize_prompt(user_msg, assistant_msg, existing_summary, existing_key_info):
    prompt = AUTO_SUMMARIZE_PROMPT + "\n\n"
    if existing_summary:
        prompt += f"已有对话摘要：{existing_summary}\n\n"
    if existing_key_info:
        prompt += f"已有关键信息：\n" + "\n".join(f"- {k}" for k in existing_key_info) + "\n\n"
    prompt += f"用户说：{user_msg}\n助手说：{assistant_msg}\n\n关键信息："
    return prompt


def build_summary_prompt(session_messages):
    text = ""
    for msg in session_messages[-20:]:
        role = "用户" if msg.get("role") == "user" else "助手"
        text += f"[{role}]: {msg.get('content', '')}\n"
    return f"请用一段话总结以下对话的核心内容：\n\n{text}\n\n总结："


class MemoryManager:
    def __init__(self):
        self.max_context_length = get_memory_config().get("max_context_length", 5000)
        self.summary_interval = get_memory_config().get("summary_interval", 10)
        self.sessions = {}

    def _load_session(self, session_id):
        path = _session_path(session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return (
                        data.get("messages", []),
                        data.get("summary", ""),
                        data.get("key_info", []),
                        data.get("digest", ""),
                    )
            except Exception:
                return [], "", "", ""
        return [], "", "", ""

    def _save_session(self, session_id, messages, summary="", key_info=None, digest=""):
        path = _session_path(session_id)
        data = {
            "messages": messages,
            "summary": summary,
            "key_info": key_info or [],
            "digest": digest,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _ensure_session(self, session_id):
        if session_id not in self.sessions:
            messages, summary, key_info, digest = self._load_session(session_id)
            if isinstance(key_info, str):
                key_info = []
            self.sessions[session_id] = {
                "messages": messages,
                "summary": summary,
                "key_info": key_info,
                "digest": digest,
                "msg_count": 0,
            }

    def get_context(self, session_id):
        self._ensure_session(session_id)
        session = self.sessions[session_id]
        return session["messages"], session["summary"], session["key_info"], session.get("digest", "")

    def add_user_message(self, session_id, content):
        self._ensure_session(session_id)
        self.sessions[session_id]["messages"].append({
            "role": "user",
            "content": content,
        })
        self.sessions[session_id]["msg_count"] = (
            self.sessions[session_id].get("msg_count", 0) + 1
        )

    def add_assistant_message(self, session_id, content):
        self._ensure_session(session_id)
        self.sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": content,
        })

    def pop_last_assistant(self, session_id):
        msgs = self.sessions[session_id]["messages"]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i]["role"] == "assistant":
                msgs.pop(i)
                return

    def get_condensed_context(self, session_id):
        messages, summary, key_info, digest = self.get_context(session_id)
        recent = messages[-self.summary_interval:] if len(messages) > self.summary_interval else messages
        total_tokens = estimate_messages_tokens(recent) + count_tokens(summary) + count_tokens(digest)
        if total_tokens <= self.max_context_length:
            return recent, summary, key_info, digest
        condensed = compress_messages(recent, self.max_context_length)
        return condensed, summary, key_info, digest

    def update_summary(self, session_id, new_summary):
        self._ensure_session(session_id)
        self.sessions[session_id]["summary"] = new_summary

    def update_key_info(self, session_id, key_info):
        self._ensure_session(session_id)
        self.sessions[session_id]["key_info"] = key_info

    def add_key_info(self, session_id, info):
        self._ensure_session(session_id)
        if info not in self.sessions[session_id]["key_info"]:
            existing = self.sessions[session_id]["key_info"]
            existing.append(info)
            if len(existing) > 50:
                self.sessions[session_id]["key_info"] = existing[-50:]

    def replace_key_info(self, session_id, new_list):
        self._ensure_session(session_id)
        self.sessions[session_id]["key_info"] = new_list[:50]

    def get_key_info(self, session_id):
        self._ensure_session(session_id)
        return self.sessions[session_id].get("key_info", [])

    def get_summary(self, session_id):
        self._ensure_session(session_id)
        return self.sessions[session_id].get("summary", "")

    def set_digest(self, session_id, digest):
        self._ensure_session(session_id)
        self.sessions[session_id]["digest"] = digest

    def get_digest(self, session_id):
        self._ensure_session(session_id)
        return self.sessions[session_id].get("digest", "")

    def save_all(self):
        for session_id, session in self.sessions.items():
            self._save_session(
                session_id,
                session["messages"],
                session.get("summary", ""),
                session.get("key_info", []),
                session.get("digest", ""),
            )

    def list_sessions(self):
        _ensure_dir()
        sessions = []
        for f in os.listdir(MEMORY_DIR):
            if f.endswith(".json"):
                session_id = f.replace(".json", "")
                path = os.path.join(MEMORY_DIR, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    sessions.append({
                        "session_id": session_id,
                        "message_count": len(data.get("messages", [])),
                        "has_summary": bool(data.get("summary", "")),
                        "has_digest": bool(data.get("digest", "")),
                        "key_info_count": len(data.get("key_info", [])),
                    })
                except Exception:
                    sessions.append({
                        "session_id": session_id,
                        "message_count": 0,
                        "has_summary": False,
                        "has_digest": False,
                        "key_info_count": 0,
                    })
        return sessions

    def delete_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]
        path = _session_path(session_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def set_max_context_length(self, length):
        self.max_context_length = length
