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


VOICE_DEFAULT = "zh-CN-XiaoxiaoNeural"

STYLE_MAP = {
    "default": None,
    "讲故事": "affectionate",
    "温柔": "gentle",
    "平静": "calm",
    "开心": "cheerful",
    "悲伤": "sad",
    "严肃": "serious",
    "生气": "angry",
    "抱歉": "sorry",
    "耳语": "whisper",
    "鼓励": "hopeful",
}


async def _tts_chunk(text, filepath, voice=VOICE_DEFAULT, style=None):
    try:
        import edge_tts
        import edge_tts.communicate as _ec
        print(f"[TTS] text({len(text)}): {text[:80]}", flush=True)
        if style:
            _orig_mkssml = _ec.mkssml
            _styledegree = ' styledegree="2"' if style == "affectionate" else ''
            def _patched_mkssml(tc, escaped_text):
                return (
                    '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                    'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="zh-CN">'
                    f'<voice name="{tc.voice}">'
                    f'<prosody pitch="{tc.pitch}" rate="{tc.rate}" volume="{tc.volume}">'
                    f'<mstts:express-as style="{style}"{_styledegree}>'
                    f'{escaped_text}'
                    '</mstts:express-as>'
                    '</prosody>'
                    '</voice>'
                    '</speak>'
                )
            _ec.mkssml = _patched_mkssml
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(filepath)
            return True
        finally:
            if style:
                _ec.mkssml = _orig_mkssml
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


def _clean_tts_text(text):
    text = re.sub(r'\[/?TOOL_CALL\]', '', text)
    text = re.sub(r'\{[^}]*?(tool|params|text|style|max_chars)[^}]*\}', '', text)
    text = re.sub(r'[（(][^)）]*?(字以内|字符|字数|不超过|限制)[^)）]*[)）]', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\[\]{}"\\]', '', text)
    text = re.sub(r'\s+', '', text).strip()
    return text


async def tts(text: str, on_chunk=None, voice=VOICE_DEFAULT, style=None, max_chars=0):
    if not text:
        return "❌ 请提供要朗读的文字"
    text = _clean_tts_text(text)
    if not text:
        return "❌ 请提供要朗读的文字"
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    print(f"[TTS] final text ({len(text)}c): [{text[:80]}]", flush=True)
    ts = int(time.time() * 1000)

    if len(text) <= MAX_CHUNK_CHARS:
        filename = f"tts_{ts}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        ok = await _tts_chunk(text, filepath, voice=voice, style=style)
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
        ok = await _tts_chunk(chunk, filepath, voice=voice, style=style)
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
    styles_desc = "、".join(STYLE_MAP.keys())
    return (
        "\n\n【工具 - 语音合成】\n"
        "当用户要求用声音输出时（包括「播放」「朗读」「讲笑话」「读一下」「生成语音」等），使用 tts 工具。\n"
        "**重要：用户要「讲笑话」「讲段子」「朗读短文」等，一律用此工具，不要用故事生成工具。**\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"tts","params":{"text":"要朗读的文字内容","style":"讲故事","max_chars":200}}[/TOOL_CALL]\n'
        f"可用风格：{styles_desc}（默认无）\n"
        "max_chars：限制朗读字数（0=不限，用户说「短一点」「100字以内」时必须设置此参数！）\n"
    )


class TtsSkill(BaseSkill):
    name = "语音合成"
    description = "将文字转为语音朗读"
    triggers = ["播放", "朗读", "读一下", "说一句话", "生成语音", "语音合成", "跟我说", "说一下"]

    async def execute(self, message, context=None):
        on_chunk = (context or {}).get("on_chunk")
        match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', message, re.DOTALL)
        tool_call_text = None
        if match:
            try:
                data = json.loads(match.group(1).strip())
                tool = data.get("tool")
                if tool == "tts":
                    params = data.get("params", {})
                    style = params.get("style")
                    if style:
                        style = STYLE_MAP.get(style)
                    return await tts(params.get("text", ""), on_chunk=on_chunk, style=style, max_chars=params.get("max_chars", 0))
            except json.JSONDecodeError:
                tool_call_text = match.group(0)

        # Keyword fallback only if no valid [TOOL_CALL] was found
        for t in self.triggers:
            if t in message:
                text = re.sub(rf'^{re.escape(t)}[\s:：]*', '', message).strip()
                if text and len(text) > 2:
                    # Skip if the extracted text is just [TOOL_CALL] remnants
                    if tool_call_text and tool_call_text in text:
                        return None
                    return await tts(text, on_chunk=on_chunk)

        return None

    def get_tools_prompt(self):
        return get_tools_prompt()
