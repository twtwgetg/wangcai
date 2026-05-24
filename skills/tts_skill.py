import json
import os
import re
import time
import subprocess
import asyncio
from skill import BaseSkill

AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

MAX_CHUNK_CHARS = 2000


def split_text_for_tts(text, max_chars=MAX_CHUNK_CHARS):
    parts = re.split(r'(?<=[。！？!?\n])', text)
    parts = [p.strip() for p in parts if p.strip()]
    chunks = []
    current = ""
    for p in parts:
        if len(current) + len(p) <= max_chars:
            current += p
        else:
            if current:
                chunks.append(current)
            if len(p) > max_chars:
                for i in range(0, len(p), max_chars):
                    chunks.append(p[i:i + max_chars])
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


def _concat_mp3(file_list, output_path):
    list_path = output_path + ".txt"
    with open(list_path, 'w', encoding='utf-8') as f:
        for fp in file_list:
            f.write(f"file '{os.path.abspath(fp)}'\n")
    subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_path, '-c', 'copy', output_path
    ], check=False, capture_output=True)
    try:
        os.remove(list_path)
    except:
        pass


async def _tts_chunk(text, filepath):
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(filepath)
        return True
    except Exception:
        try:
            import pyttsx3
            wav_path = filepath.replace(".mp3", ".wav")
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                if "ZH-CN" in v.id:
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 180)
            engine.save_to_file(text, wav_path)
            engine.runAndWait()
            subprocess.run(['ffmpeg', '-y', '-i', wav_path, '-b:a', '128k', filepath],
                           check=False, capture_output=True)
            try:
                os.remove(wav_path)
            except:
                pass
            return os.path.exists(filepath)
        except:
            return False


async def tts(text: str, on_chunk=None):
    if not text:
        return "❌ 请提供要朗读的文字"
    ts = int(time.time() * 1000)

    if len(text) <= MAX_CHUNK_CHARS:
        filename = f"tts_{ts}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        ok = await _tts_chunk(text, filepath)
        if not ok or not os.path.exists(filepath):
            return "❌ 语音生成失败"
        url = f"/static/audio/{filename}"
        return f"🔊 {text[:40]}{'...' if len(text) > 40 else ''}\n[AUDIO]{url}[/AUDIO]"

    chunks = split_text_for_tts(text)
    if on_chunk:
        await on_chunk(f"📢 文本较长，将分{len(chunks)}段生成语音...\n")

    temp_files = []
    for i, chunk in enumerate(chunks):
        if on_chunk:
            await on_chunk(f"⏳ 正在生成第{i+1}/{len(chunks)}段...\n")
        filepath = os.path.join(AUDIO_DIR, f"tts_{ts}_{i}.mp3")
        ok = await _tts_chunk(chunk, filepath)
        if ok and os.path.exists(filepath):
            temp_files.append(filepath)

    if not temp_files:
        return "❌ 语音生成失败"

    output_path = os.path.join(AUDIO_DIR, f"tts_{ts}_long.mp3")
    _concat_mp3(temp_files, output_path)

    for f in temp_files:
        try:
            os.remove(f)
        except:
            pass

    if not os.path.exists(output_path):
        return "❌ 语音合并失败"
    url = f"/static/audio/tts_{ts}_long.mp3"
    preview = text[:40].replace('\n', ' ')
    return f"🔊 {preview}{'...' if len(text) > 40 else ''}\n[AUDIO]{url}[/AUDIO]"


def get_tools_prompt():
    return (
        "\n\n【工具 - 语音合成】\n"
        "当用户要求用语音朗读文本、说一句话、或生成语音时，使用 tts 工具。\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"tts","params":{"text":"要朗读的文字内容"}}[/TOOL_CALL]\n'
    )


class TtsSkill(BaseSkill):
    name = "语音合成"
    description = "将文字转为语音朗读"
    triggers = ["朗读", "读一下", "说一句话", "生成语音", "语音合成", "跟我说", "说一下"]

    async def execute(self, message, context=None):
        on_chunk = (context or {}).get("on_chunk")
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                if tool == "tts":
                    return await tts(data.get("params", {}).get("text", ""), on_chunk=on_chunk)
            except json.JSONDecodeError:
                pass

        for t in self.triggers:
            if t in message:
                text = re.sub(rf'^{re.escape(t)}[\s:：]*', '', message).strip()
                if text and len(text) > 2:
                    return await tts(text, on_chunk=on_chunk)

        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
