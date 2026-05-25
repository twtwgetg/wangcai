import json
import os
import time
from config import get_character_config

CHARACTERS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    get_character_config().get("profiles_path", "characters"),
)

_ts = lambda: time.strftime("%H:%M:%S")


def _log(msg):
    print(f"[CHAR {_ts()}] {msg}")


def _list_character_files():
    if not os.path.exists(CHARACTERS_DIR):
        os.makedirs(CHARACTERS_DIR, exist_ok=True)
    files = []
    for f in os.listdir(CHARACTERS_DIR):
        if f.endswith(".json"):
            files.append(f)
    return sorted(files)


class CharacterManager:
    def __init__(self):
        self.profiles = {}
        self.current_name = get_character_config().get("current", "default")
        _log(f"__init__ current_name={self.current_name}")
        self._load_all()

    def _load_all(self):
        files_found = _list_character_files()
        _log(f"_load_all files={files_found} dir={CHARACTERS_DIR}")
        for filename in files_found:
            name = filename.replace(".json", "")
            path = os.path.join(CHARACTERS_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.profiles[name] = json.load(f)
                p = self.profiles[name]
                _log(f"_load_all loaded {name}: identity[:50]={str(p.get('identity',''))[:50]}")
            except Exception as e:
                _log(f"_load_all FAIL {filename}: {e}")

        if "default" not in self.profiles:
            _log("_load_all default not found, creating default profile")
            self.profiles["default"] = {
                "name": "旺财",
                "description": "一个友好的 AI 助手",
                "identity": "你是旺财，一个智能 AI 助手。",
                "traits": ["友好", "乐于助人", "知识丰富"],
                "knowledge": [],
                "rules": ["用中文回答用户的问题"],
                "example_dialogs": [],
            }
            self._save("default")

        if self.current_name not in self.profiles:
            _log(f"_load_all current_name {self.current_name} not found, falling back to default")
            self.current_name = "default"

    def _save(self, name):
        path = os.path.join(CHARACTERS_DIR, f"{name}.json")
        data = self.profiles[name]
        identity_preview = str(data.get("identity", ""))[:60]
        _log(f"_save {name} -> {path} identity[:60]={identity_preview}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        _log(f"_save done exists={exists} size={size}")

    def list_characters(self):
        result = []
        for name, profile in self.profiles.items():
            entry = {
                "name": name,
                "display_name": profile.get("name", name),
                "description": profile.get("description", ""),
                "current": name == self.current_name,
            }
            result.append(entry)
        _log(f"list_characters -> {[e['name']+'('+e['display_name']+')' + ('*' if e['current'] else '') for e in result]}")
        return result

    def get_current(self):
        p = self.profiles.get(self.current_name, self.profiles.get("default", {}))
        _log(f"get_current() -> name={self.current_name} identity[:50]={str(p.get('identity',''))[:50]}")
        return p

    def get_current_name(self):
        return self.current_name

    def switch_to(self, name):
        _log(f"switch_to({name}) profiles={list(self.profiles.keys())}")
        if name in self.profiles:
            self.current_name = name
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "config.json"
            )
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            config_data["character"]["current"] = name
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            _log(f"switch_to OK current_name={name}, config.json updated")
            return True
        _log(f"switch_to FAIL: {name} not in profiles")
        return False

    def reload_current(self):
        name = self.current_name
        path = os.path.join(CHARACTERS_DIR, f"{name}.json")
        _log(f"reload_current name={name} path_exists={os.path.exists(path)}")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.profiles[name] = json.load(f)
                p = self.profiles[name]
                _log(f"reload_current OK identity[:50]={str(p.get('identity',''))[:50]}")
            except Exception as e:
                _log(f"reload_current FAIL: {e}")
        return self.profiles.get(name, {})

    def get_profile(self, name):
        p = self.profiles.get(name)
        _log(f"get_profile({name}) found={'yes' if p else 'no'} identity[:50]={str(p.get('identity',''))[:50] if p else 'N/A'}")
        return p

    def save_profile(self, name, profile, original_name=None):
        _log(f"save_profile ENTER name={name} original_name={original_name}")
        incoming_identity = str(profile.get("identity", ""))[:60]
        _log(f"save_profile incoming identity[:60]={incoming_identity}")

        if name == "default" and original_name and original_name != name:
            _log("save_profile REJECTED: rename to default")
            return False
        if original_name == "default" and name != "default":
            _log("save_profile REJECTED: rename from default")
            return False

        existing = self.profiles.get(original_name or name, {})
        _log(f"save_profile existing identity[:50]={str(existing.get('identity',''))[:50] if existing else 'N/A'}")

        if profile.get("example_dialogs") is None:
            profile["example_dialogs"] = existing.get("example_dialogs", [])
            _log(f"save_profile merged example_dialogs count={len(profile['example_dialogs'])}")

        is_rename = (original_name and original_name != name
                     and original_name in self.profiles
                     and name not in self.profiles)
        _log(f"save_profile is_rename={is_rename}")

        self.profiles[name] = profile
        _log(f"save_profile set self.profiles[{name}]")

        self._save(name)

        if is_rename:
            old_path = os.path.join(CHARACTERS_DIR, f"{original_name}.json")
            _log(f"save_profile rename: deleting old {old_path}")
            if os.path.exists(old_path):
                os.remove(old_path)
            del self.profiles[original_name]
            if original_name == self.current_name:
                self.current_name = name
                config_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "config.json"
                )
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                config_data["character"]["current"] = name
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                _log(f"save_profile updated config.json current={name}")

        if name == self.current_name:
            self.reload_current()

        # Final verification: read from disk
        disk_path = os.path.join(CHARACTERS_DIR, f"{name}.json")
        if os.path.exists(disk_path):
            with open(disk_path, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            _log(f"save_profile VERIFY on disk identity[:50]={str(on_disk.get('identity',''))[:50]}")
        else:
            _log(f"save_profile VERIFY FAIL: file NOT FOUND at {disk_path}")

        _log("save_profile RETURN True")
        return True

    def delete_profile(self, name):
        if name == "default":
            return False
        if name in self.profiles:
            del self.profiles[name]
            path = os.path.join(CHARACTERS_DIR, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
            if self.current_name == name:
                self.current_name = "default"
            return True
        return False

    def build_system_prompt(self, memory_summary=""):
        profile = self.get_current()
        parts = []

        from datetime import datetime
        parts.append(f"当前日期时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}（周{['一','二','三','四','五','六','日'][datetime.now().weekday()]}）")
        parts.append("")

        identity = profile.get("identity", "你是旺财，一个智能 AI 助手。")
        parts.append(identity)

        traits = profile.get("traits", [])
        if traits:
            parts.append("你的性格特点：" + "、".join(traits))

        knowledge = profile.get("knowledge", [])
        if knowledge:
            parts.append("你知道的信息：" + "；".join(knowledge))

        rules = profile.get("rules", [])
        if rules:
            parts.append("行为规则：")
            for i, r in enumerate(rules, 1):
                parts.append(f"{i}. {r}")

        examples = profile.get("example_dialogs", [])
        if examples:
            parts.append("对话示例：")
            for ex in examples:
                parts.append(f"用户：{ex.get('user', '')}")
                parts.append(f"你：{ex.get('assistant', '')}")

        if memory_summary:
            parts.append(f"\n长期记忆信息：\n{memory_summary}")

        return "\n".join(parts)
