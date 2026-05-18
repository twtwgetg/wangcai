import json
import os
from config import get_character_config

CHARACTERS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    get_character_config().get("profiles_path", "characters"),
)


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
        self._load_all()

    def _load_all(self):
        for filename in _list_character_files():
            name = filename.replace(".json", "")
            path = os.path.join(CHARACTERS_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.profiles[name] = json.load(f)
            except Exception as e:
                print(f"加载角色 {filename} 失败: {e}")

        if "default" not in self.profiles:
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
            self.current_name = "default"

    def _save(self, name):
        path = os.path.join(CHARACTERS_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.profiles[name], f, ensure_ascii=False, indent=2)

    def list_characters(self):
        result = []
        for name, profile in self.profiles.items():
            result.append({
                "name": name,
                "display_name": profile.get("name", name),
                "description": profile.get("description", ""),
                "current": name == self.current_name,
            })
        return result

    def get_current(self):
        return self.profiles.get(self.current_name, self.profiles.get("default", {}))

    def get_current_name(self):
        return self.current_name

    def switch_to(self, name):
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
            return True
        return False

    def reload_current(self):
        name = self.current_name
        path = os.path.join(CHARACTERS_DIR, f"{name}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.profiles[name] = json.load(f)
            except Exception:
                pass
        return self.profiles.get(name, {})

    def get_profile(self, name):
        return self.profiles.get(name)

    def save_profile(self, name, profile):
        self.profiles[name] = profile
        self._save(name)

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
