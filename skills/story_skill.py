import json
import os
import re
import time
import asyncio
import httpx
from skill import BaseSkill


def _get_llm_config():
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f).get("llm", {})
    except:
        cfg = {}
    return {
        "api_url": os.environ.get("MODEL_API_URL", cfg.get("api_url", "http://127.0.0.1:8080/v1")),
        "model": os.environ.get("MODEL_NAME", cfg.get("model_name", "")),
        "api_key": cfg.get("api_key", ""),
    }


STORY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "stories")
os.makedirs(STORY_DIR, exist_ok=True)

CHUNK_SIZE = 1500


async def _llm_gen(prompt, system="你是一个故事作家。只输出故事内容，不要有任何额外说明。"):
    llm = _get_llm_config()
    headers = {"Content-Type": "application/json"}
    if llm["api_key"]:
        headers["Authorization"] = f"Bearer {llm['api_key']}"
    async with httpx.AsyncClient(timeout=120.0) as cl:
        r = await cl.post(
            f"{llm['api_url']}/chat/completions",
            headers=headers,
            json={
                "model": llm["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "temperature": 0.8,
                "max_tokens": 2048,
            },
        )
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


async def generate_long_story(theme, total_chars=20000, on_chunk=None):
    chunk_count = max(3, total_chars // CHUNK_SIZE)
    parts = []

    sys_prompt = (
        "你是一个中文长篇故事作家。请根据要求创作故事。\n"
        "要求：\n"
        "- 用中文写作\n"
        "- 语言生动，情节丰富\n"
        "- 每段约1500字\n"
        "- 只输出故事正文，不要标题、说明或额外标记"
    )

    summary = ""
    for i in range(chunk_count):
        if on_chunk:
            await on_chunk(f"📝 正在创作第{i+1}/{chunk_count}段...\n")

        is_first = i == 0
        is_last = i == chunk_count - 1

        if is_first:
            prompt = f"请写一个故事的开头。故事主题：{theme}\n\n直接输出故事正文："
        else:
            prompt = f"继续这个故事，接续下面的内容：\n\n{summary[-300:]}\n\n直接输出接下来的故事正文："
        if is_last:
            prompt += "\n\n这是故事的结尾部分，请给出一个完整的收尾。"

        content = await _llm_gen(prompt, sys_prompt)
        if content:
            parts.append(content)
            summary = content

        await asyncio.sleep(0.5)

    return "\n\n".join(parts)


DEFAULT_STORY_CHARS = 3000


def get_tools_prompt():
    return (
        "\n\n【工具 - 故事生成朗读】\n"
        "仅当用户明确要求创作长篇原创故事/小说（并朗读）时使用此工具。\n"
        "**注意：用户要「讲笑话」不属于此工具，请用「语音合成」工具的 max_chars 限制字数即可。**\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"generate_story","params":{"theme":"故事主题","total_chars":3000}}[/TOOL_CALL]\n'
        "total_chars：总字数，短篇 1000-5000，中篇 5000-10000，长篇 10000-30000（默认 3000）\n"
    )


class StorySkill(BaseSkill):
    name = "长篇故事生成"
    description = "创作长篇原创故事（3000字以上）并转为语音朗读，笑话/段子勿用"
    triggers = ["写长篇小说", "创作长篇故事", "生成中篇小说", "写小说"]

    async def execute(self, message, context=None):
        on_chunk = (context or {}).get("on_chunk")

        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                if tool == "generate_story":
                    params = data.get("params", {})
                    theme = params.get("theme", "")
                    total_chars = params.get("total_chars", 0) or DEFAULT_STORY_CHARS
                    if not theme:
                        return "❌ 请提供故事主题"
                    return await _do_generate(theme, total_chars, on_chunk)
            except json.JSONDecodeError:
                pass

        for t in self.triggers:
            if t in message:
                text = re.sub(rf'^{re.escape(t)}[\s:：]*', '', message).strip()
                if text and len(text) > 2:
                    return await _do_generate(text, DEFAULT_STORY_CHARS, on_chunk)

        return None

    def get_tools_prompt(self):
        return get_tools_prompt()


async def _do_generate(theme, total_chars, on_chunk):
    ts = int(time.time() * 1000)

    if on_chunk:
        await on_chunk(f"📚 开始创作故事「{theme[:30]}」...\n")

    full_text = await generate_long_story(theme, total_chars, on_chunk)

    if len(full_text) < 50:
        return "❌ 故事生成失败"

    # Save story text file
    text_filename = f"story_{ts}.txt"
    text_filepath = os.path.join(STORY_DIR, text_filename)
    with open(text_filepath, "w", encoding="utf-8") as f:
        f.write(full_text)

    if on_chunk:
        await on_chunk(f"✅ 故事创作完成，共{len(full_text)}字\n")
        await on_chunk(f"🔊 正在将故事转为语音...\n")

    from tts_skill import tts
    result = await tts(full_text, on_chunk=on_chunk, style="affectionate")

    text_url = f"/static/stories/{text_filename}"
    return result + f"\n📄 故事原文：{text_url}"
