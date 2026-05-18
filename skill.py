import importlib
import os
import inspect
import sys

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


class BaseSkill:
    name = ""
    description = ""
    triggers = []

    def matches(self, message):
        for trigger in self.triggers:
            if trigger in message.lower():
                return True
        return False

    async def execute(self, message, context=None):
        raise NotImplementedError


class SkillEngine:
    def __init__(self):
        self.skills = {}
        self._load_skills()

    def _load_skills(self):
        if SKILLS_DIR not in sys.path:
            sys.path.insert(0, SKILLS_DIR)

        for f in os.listdir(SKILLS_DIR):
            if f.endswith(".py") and f != "__init__.py":
                module_name = f[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, os.path.join(SKILLS_DIR, f)
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        for name, obj in inspect.getmembers(module):
                            if (
                                inspect.isclass(obj)
                                and issubclass(obj, BaseSkill)
                                and obj != BaseSkill
                            ):
                                instance = obj()
                                self.skills[instance.name] = instance
                except Exception as e:
                    print(f"加载技能 {f} 失败: {e}")

    def reload_skills(self):
        self.skills = {}
        self._load_skills()

    def list_skills(self):
        result = []
        for name, skill in self.skills.items():
            result.append({
                "name": skill.name,
                "description": skill.description,
                "triggers": skill.triggers,
            })
        return result

    async def process_message(self, message, context=None):
        for name, skill in self.skills.items():
            if skill.matches(message):
                try:
                    result = await skill.execute(message, context)
                    if result:
                        return result
                except Exception as e:
                    return f"[技能 {name}] 执行出错: {e}"
        return None

    def get_tools_prompt(self):
        prompts = []
        for name, skill in self.skills.items():
            if hasattr(skill, 'get_tools_prompt'):
                p = skill.get_tools_prompt()
                if p:
                    prompts.append(p)
        return "\n".join(prompts)

    async def execute_tool_call(self, text, context=None):
        for name, skill in self.skills.items():
            try:
                result = await skill.execute(text, context)
                if result:
                    return result
            except Exception:
                continue
        return None
