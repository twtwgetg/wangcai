import os
import httpx
import re
import json
import asyncio
import logging
import sys
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, List, Optional

logger = logging.getLogger("feishu")

from config import load_config, save_config, get_llm_config, get_server_config
from character import CharacterManager
from memory import MemoryManager
from skill import SkillEngine

_stt_process = None


def _start_stt_server():
    global _stt_process
    py310 = r"C:\Users\xuqua\miniconda3\envs\py310\python.exe"
    if not os.path.exists(py310):
        print("[STT] py310 not found, skipping STT server")
        return
    script = os.path.join(os.path.dirname(__file__), "relay_server", "stt_server.py")
    log = open(os.path.join(os.path.dirname(__file__), "stt_stdout.log"), "w", encoding="utf-8")
    try:
        _stt_process = subprocess.Popen([py310, "-u", script], stdout=log, stderr=subprocess.STDOUT)
        print(f"[STT] Server started (PID {_stt_process.pid})")
    except Exception as e:
        print(f"[STT] Failed to start: {e}")


app = FastAPI(title="旺财 AI 助手")

app.mount("/static", StaticFiles(directory="public"), name="static")

char_mgr = CharacterManager()
mem_mgr = MemoryManager()
skill_engine = SkillEngine()

llm_config = get_llm_config()
MODEL_API_URL = os.environ.get("MODEL_API_URL", llm_config.get("api_url", "http://127.0.0.1:8080/v1"))
MODEL_NAME = os.environ.get("MODEL_NAME", llm_config.get("model_name", "llama-2-7b-chat"))
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", llm_config.get("api_key", ""))

feishu_bot = None

print(f"[Model] API: {MODEL_API_URL}")
print(f"[Model] Name: {MODEL_NAME}")
print(f"[Role] {char_mgr.get_current_name()}")
print(f"[Memory] Context limit: {mem_mgr.max_context_length}")
print(f"[Skills] Loaded: {len(skill_engine.skills)}")


_feishu_ws_thread = None

def init_feishu(force=False):
    global feishu_bot, _feishu_ws_thread
    if feishu_bot is None or force:
        from feishu_bot import FeishuBot
        feishu_bot = FeishuBot(message_handler=handle_feishu_message)
        if feishu_bot.enabled:
            logger.info("飞书机器人已启用 app_id=%s...", feishu_bot.app_id[:8])
        else:
            logger.info("飞书机器人未启用")

async def start_feishu_ws():
    global _feishu_ws_thread
    if feishu_bot and feishu_bot.enabled:
        await feishu_bot.start_ws_listener()
        logger.info("飞书 WS 监听已启动")


async def handle_feishu_message(session_id: str, message: str, source: str = "feishu"):
    logger.info("处理消息: %s", message[:200])
    full_response = ""
    error_msg = None

    async def on_chunk(chunk):
        nonlocal full_response
        full_response += chunk

    try:
        await send_to_llm(message, session_id, on_chunk, source=source)
        if not full_response.strip():
            error_msg = "模型返回为空，请检查模型服务是否正常"
    except Exception as e:
        error_msg = "处理消息时出错: %s" % e
        logger.error("处理错误: %s", e)

    if error_msg:
        logger.info("返回错误: %s", error_msg)
        return error_msg
    logger.info("回复: %s", full_response[:200])
    return full_response or "已收到"


@app.get("/")
async def root():
    with open("public/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


async def _handle_audio_bytes(websocket, audio_bytes, session_id):
    """Transcribe binary audio and process as chat message."""
    import aiohttp
    text = ""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", audio_bytes, filename="audio.webm", content_type="audio/webm")
            async with session.post("http://127.0.0.1:9528/stt", data=data,
                                    timeout=aiohttp.ClientTimeout(60)) as resp:
                if resp.status != 200:
                    await websocket.send_json({"type": "chunk", "content": "❌ 语音识别失败"})
                    await websocket.send_json({"type": "done"})
                    return
                result = await resp.json()
                text = result.get("text", "").strip()
                if not text:
                    await websocket.send_json({"type": "chunk", "content": "❌ 未识别到语音"})
                    await websocket.send_json({"type": "done"})
                    return
    except Exception as e:
        await websocket.send_json({"type": "chunk", "content": f"❌ 语音服务异常: {e}"})
        await websocket.send_json({"type": "done"})
        return

    async def handle_chunk(chunk):
        await websocket.send_json({"type": "chunk", "content": chunk})
    async def handle_reset():
        pass
    try:
        await send_to_llm(text, session_id, handle_chunk, source="web", on_reset=handle_reset)
    except Exception as e:
        await websocket.send_json({"type": "chunk", "content": f"❌ LLM 处理失败: {e}"})
    await websocket.send_json({"type": "done"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    session_id = f"session_{client_id}"

    print(f"客户端连接：{client_id}")

    try:
        while True:
            raw = await websocket.receive()
            if raw.get("bytes"):
                await _handle_audio_bytes(websocket, raw["bytes"], session_id)
                continue
            data = raw.get("text", "")
            if not data:
                continue
            message_data = json.loads(data)
            msg_type = message_data.get("type", "chat")

            if msg_type == "chat":
                user_message = message_data.get("message", "")
                session_id = message_data.get("session_id", session_id)
                print(f"收到消息：{user_message[:50]}...")

                msg_lower = user_message.strip().lower()
                if msg_lower == "/help":
                    help_text = (
                        "📚 可用命令：\n\n"
                        "📱 /wechat \"联系人\" \"消息\" - 给微信联系人发送消息\n"
                        "  示例：/wechat \"文件传输助手\" \"你好\"\n\n"
                        "🧠 /memory - 查看当前会话记忆\n"
                        "🔄 /clearmemory - 清除当前会话记忆\n\n"
                        "💡 更多功能请在设置面板中配置"
                    )
                    await websocket.send_json({"type": "chunk", "content": help_text})
                    await websocket.send_json({"type": "done"})
                    continue

                # pre-LLM video stop — avoid relying on LLM to call tool
                if any(w in msg_lower for w in ["关闭视频", "停止播放", "关闭电影", "暂停视频"]):
                    await websocket.send_json({"type": "video_stop"})
                    await websocket.send_json({"type": "chunk", "content": "⏹️ 视频已关闭"})
                    await websocket.send_json({"type": "done"})
                    continue

                async def handle_chunk(chunk):
                    await websocket.send_json({"type": "chunk", "content": chunk})

                async def handle_reset():
                    await websocket.send_json({"type": "clear_stream"})

                await send_to_llm(user_message, session_id, handle_chunk, source="web", on_reset=handle_reset)
                await websocket.send_json({"type": "done"})

            elif msg_type == "command":
                cmd = message_data.get("command", "")
                params = message_data.get("params", {})

                if cmd == "clear_memory":
                    session_id = params.get("session_id", session_id)
                    mem_mgr.delete_session(session_id)
                    await websocket.send_json({"type": "command_result", "command": cmd, "success": True})

                elif cmd == "get_sessions":
                    sessions = mem_mgr.list_sessions()
                    await websocket.send_json({"type": "command_result", "command": cmd, "data": sessions})

            elif msg_type == "get_characters":
                chars = char_mgr.list_characters()
                await websocket.send_json({"type": "characters", "data": chars})

            elif msg_type == "switch_character":
                name = message_data.get("name", "")
                success = char_mgr.switch_to(name)
                await websocket.send_json({"type": "character_switched", "success": success, "name": name})

            elif msg_type == "get_character_detail":
                name = message_data.get("name", "")
                profile = char_mgr.get_profile(name)
                detail_preview = str(profile.get("identity",""))[:50] if profile else "N/A"
                print(f"[SVR] get_character_detail({name}) identity[:50]={detail_preview}")
                await websocket.send_json({"type": "character_detail", "data": profile})

            elif msg_type == "save_character":
                name = message_data.get("name", "")
                profile = message_data.get("profile", {})
                original_name = message_data.get("original_name") or name
                incoming_identity = str(profile.get("identity",""))[:60]
                print(f"[SVR] save_character ENTER name={name} original_name={original_name} identity[:60]={incoming_identity}")
                success = char_mgr.save_profile(name, profile, original_name)
                print(f"[SVR] save_character DONE success={success}")
                await websocket.send_json({"type": "character_saved", "success": success, "name": name})

            elif msg_type == "delete_character":
                name = message_data.get("name", "")
                success = char_mgr.delete_profile(name)
                await websocket.send_json({"type": "character_deleted", "success": success})

            elif msg_type == "get_config":
                config = load_config()
                await websocket.send_json({"type": "config", "data": config})

            elif msg_type == "save_config":
                new_config = message_data.get("config", {})
                existing = load_config()
                for key in new_config:
                    existing[key] = new_config[key]
                save_config(existing)
                global MODEL_API_URL, MODEL_NAME, MODEL_API_KEY
                MODEL_API_URL = existing.get("llm", {}).get("api_url", MODEL_API_URL)
                MODEL_NAME = existing.get("llm", {}).get("model_name", MODEL_NAME)
                MODEL_API_KEY = existing.get("llm", {}).get("api_key", MODEL_API_KEY)
                mem_mgr.set_max_context_length(
                    existing.get("memory", {}).get("max_context_length", 5000)
                )
                await websocket.send_json({"type": "config_saved", "success": True})

            elif msg_type == "get_memory":
                session_id = message_data.get("session_id", session_id)
                _, summary, key_info, digest = mem_mgr.get_context(session_id)
                memos = []
                global_memos = []
                try:
                    import json as _json
                    memo_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "memory_store", "memos"
                    )
                    safe = session_id.replace("/", "_").replace("\\", "_").replace(":", "_")
                    session_memo_file = os.path.join(memo_path, f"{safe}.json")
                    global_memo_file = os.path.join(memo_path, "_global.json")
                    if os.path.exists(session_memo_file):
                        with open(session_memo_file, "r", encoding="utf-8") as f:
                            memos = _json.load(f)
                    if os.path.exists(global_memo_file):
                        with open(global_memo_file, "r", encoding="utf-8") as f:
                            global_memos = _json.load(f)
                except Exception:
                    pass
                await websocket.send_json({
                    "type": "memory",
                    "data": {
                        "summary": summary,
                        "key_info": key_info,
                        "digest": digest,
                        "memos": memos[-20:],
                        "global_memos": global_memos[-20:],
                    }
                })

            elif msg_type == "summarize_now":
                sid = message_data.get("session_id", session_id)
                await websocket.send_json({"type": "chunk", "content": "🤖 正在生成重点摘要...\n"})
                result = await generate_digest(sid)
                mem_mgr.set_digest(sid, result)
                mem_mgr.save_all()
                await websocket.send_json({"type": "chunk", "content": "✅ 摘要已更新\n"})
                _, _, _, digest = mem_mgr.get_context(sid)
                await websocket.send_json({
                    "type": "memory",
                    "data": {
                        "summary": mem_mgr.get_summary(sid),
                        "key_info": mem_mgr.get_key_info(sid),
                        "digest": digest,
                    }
                })
                await websocket.send_json({"type": "done"})

            elif msg_type == "get_sessions_list":
                sessions = mem_mgr.list_sessions()
                await websocket.send_json({"type": "sessions_list", "data": sessions})

            elif msg_type == "delete_session":
                sid = message_data.get("session_id", "")
                success = mem_mgr.delete_session(sid)
                await websocket.send_json({"type": "session_deleted", "success": success, "session_id": sid})

            elif msg_type == "get_skills":
                skills = skill_engine.list_skills()
                await websocket.send_json({"type": "skills_list", "data": skills})

            elif msg_type == "reload_skills":
                skill_engine.reload_skills()
                skills = skill_engine.list_skills()
                await websocket.send_json({"type": "skills_reloaded", "data": skills})

            elif msg_type == "get_feishu_config":
                init_feishu()
                if feishu_bot:
                    await websocket.send_json({
                        "type": "feishu_config",
                        "data": feishu_bot.get_config_info()
                    })

            elif msg_type == "save_feishu_config":
                fb_config = message_data.get("config", {})
                if feishu_bot:
                    feishu_bot.update_config(
                        enabled=fb_config.get("enabled"),
                        app_id=fb_config.get("app_id"),
                        app_secret=fb_config.get("app_secret"),
                        receive_id=fb_config.get("receive_id"),
                        receive_id_type=fb_config.get("receive_id_type"),
                        bot_name=fb_config.get("bot_name"),
                    )
                init_feishu(force=True)
                await start_feishu_ws()
                await websocket.send_json({"type": "feishu_config_saved", "success": True})

            elif msg_type == "test_feishu":
                if not feishu_bot or not feishu_bot.enabled:
                    await websocket.send_json({
                        "type": "test_feishu_result",
                        "success": False,
                        "msg": "飞书未启用，请先保存配置",
                    })
                else:
                    ok = await feishu_bot.check_connection()
                    await websocket.send_json({
                        "type": "test_feishu_result",
                        "success": ok,
                        "msg": "飞书连接成功" if ok else "飞书连接失败，请检查 app_id 和 app_secret",
                    })

            elif msg_type == "test_model":
                cfg = message_data.get("config", {})
                test_url = cfg.get("api_url", MODEL_API_URL)
                test_model = cfg.get("model_name", MODEL_NAME)
                test_key = cfg.get("api_key", MODEL_API_KEY)
                try:
                    headers = {"Content-Type": "application/json"}
                    if test_key:
                        headers["Authorization"] = f"Bearer {test_key}"
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            f"{test_url}/chat/completions",
                            headers=headers,
                            json={
                                "model": test_model,
                                "messages": [{"role": "user", "content": "回复'连接成功'即可"}],
                                "max_tokens": 50,
                                "stream": False,
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            reply = data["choices"][0]["message"]["content"]
                            await websocket.send_json({
                                "type": "test_model_result",
                                "success": True,
                                "response": reply[:200],
                            })
                        else:
                            await websocket.send_json({
                                "type": "test_model_result",
                                "success": False,
                                "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                            })
                except Exception as e:
                    await websocket.send_json({
                        "type": "test_model_result",
                        "success": False,
                        "error": str(e),
                    })

    except WebSocketDisconnect:
        print(f"客户端断开：{client_id}")
    except Exception as e:
        print(f"错误：{e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


async def call_llm(messages, max_tokens=200, stream=False):
    """通用 LLM 调用，返回完整响应文本"""
    headers = {"Content-Type": "application/json"}
    if MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {MODEL_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MODEL_API_URL}/chat/completions",
                headers=headers,
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": stream,
                    "temperature": 0.3,
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None


async def extract_key_points(session_id, user_msg, assistant_msg):
    """自动提取本轮对话的关键信息并更新记忆"""
    from memory import build_summarize_prompt
    existing = mem_mgr.get_summary(session_id)
    existing_keys = mem_mgr.get_key_info(session_id)
    prompt_text = build_summarize_prompt(user_msg, assistant_msg, existing, existing_keys)
    result = await call_llm([{"role": "user", "content": prompt_text}], max_tokens=300)
    if result and result.strip() != "无":
        lines = [l.strip().lstrip("- ") for l in result.split("\n") if l.strip() and l.strip() != "无"]
        for line in lines:
            if len(line) > 5:
                mem_mgr.add_key_info(session_id, line)
        mem_mgr.save_all()


async def generate_digest(session_id):
    """用 LLM 生成对话重点摘要"""
    from memory import build_summary_prompt
    messages, _, _, _ = mem_mgr.get_context(session_id)
    if not messages:
        return "暂无对话内容"
    prompt_text = build_summary_prompt(messages)
    result = await call_llm([{"role": "user", "content": prompt_text}], max_tokens=400)
    return result or "摘要生成失败"


async def send_to_llm(message: str, session_id: str, on_chunk, source: str = "web", on_reset=None):
    wechat_pattern = r'/wechat\s+["\']?([^"\']+)["\']?\s+["\']?(.+)["\']?$'
    match = re.match(wechat_pattern, message)
    if match:
        contact_name = match.group(1)
        chat_message = match.group(2)
        from wechat_auto import search_and_chat
        await on_chunk(f"📱 正在给 '{contact_name}' 发送消息...\n")
        loop = asyncio.get_event_loop()

        def run_wechat():
            try:
                result = search_and_chat(contact_name, chat_message, auto_find_window=True)
                if result and result.startswith("❌"):
                    return False, result
                return True, None
            except Exception as e:
                return False, str(e)

        success, error = await loop.run_in_executor(None, run_wechat)
        if success:
            await on_chunk(f"✅ 已给 '{contact_name}' 发送消息：{chat_message}\n")
        else:
            await on_chunk(f"❌ 执行失败：{error}\n")
        return

    mem_mgr.add_user_message(session_id, message)

    condensed_messages, summary, key_info, digest = mem_mgr.get_condensed_context(session_id)

    memory_summary = ""
    if summary:
        memory_summary += f"对话摘要：{summary}\n"
    if key_info:
        from memory import count_tokens
        max_key_tokens = 300
        items = []
        for k in reversed(key_info):
            item = f"- {k}"
            if count_tokens("\n".join(items + [item])) > max_key_tokens:
                break
            items.append(item)
        if items:
            memory_summary += "关键信息：\n" + "\n".join(items)
            if len(items) < len(key_info):
                memory_summary += f"\n...及其他 {len(key_info) - len(items)} 条记忆"
    if digest:
        memory_summary += f"\n重点摘要：{digest}\n"

    # 跨会话的全局习惯/偏好（_global.json）
    _gpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_store", "memos", "_global.json")
    if os.path.exists(_gpath):
        try:
            with open(_gpath, "r", encoding="utf-8") as _gf:
                _gmemos = json.load(_gf)
            if _gmemos:
                from memory import count_tokens as _ct
                _gitems = []
                for _gm in reversed(_gmemos):
                    _line = f"- {_gm.get('content','')}"
                    if _ct("\n".join(_gitems + [_line])) > 400:
                        break
                    _gitems.append(_line)
                if _gitems:
                    memory_summary += "\n用户习惯（跨会话长期记忆）：\n" + "\n".join(_gitems)
        except Exception:
            pass

    system_prompt = char_mgr.build_system_prompt(memory_summary)
    tools_prompt = skill_engine.get_tools_prompt()
    if tools_prompt:
        system_prompt += "\n\n" + tools_prompt
    system_prompt += (
        "\n\n【工具 - 长期记忆】\n"
        "当用户要求你「记住」任何信息时（生日、称呼、偏好、习惯等），一律使用 remember_global 存入跨会话长期记忆。\n"
        "当用户要求你「忘记/删除」某些信息时，使用 forget_global 删除对应的长期记忆。\n"
        "这是强制要求：用户说「记住XX」时你必须调用工具，不能只是口头答应。\n"
        "调用格式：\n"
        '[TOOL_CALL]{"tool":"remember_global","params":{"content":"用户的生日是1979年7月3日","tags":"用户信息"}}[/TOOL_CALL]\n'
        '[TOOL_CALL]{"tool":"forget_global","params":{"content":"生日"}}[/TOOL_CALL]\n'
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(condensed_messages)
    messages.append({"role": "user", "content": message})

    full_response = ""

    try:
        headers = {"Content-Type": "application/json"}
        if MODEL_API_KEY:
            headers["Authorization"] = f"Bearer {MODEL_API_KEY}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{MODEL_API_URL}/chat/completions",
                headers=headers,
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": True,
                    "temperature": llm_config.get("temperature", 0.7),
                    "max_tokens": llm_config.get("max_tokens", 2048),
                },
            )

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = (
                            data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if content:
                            full_response += content
                            await on_chunk(content)
                    except json.JSONDecodeError:
                        continue

        def _check_hallucination(text):
            if re.search(r'\[TOOL_CALL\]', text):
                return False
            action_words = r'(?:删除|创建|复制|移动|重命名|新建)'
            result_words = r'(?:成功|完成|好了|已经|已)'
            if re.search(f'{result_words}.*{action_words}', text):
                return True
            if re.search(f'{action_words}.*{result_words}', text):
                return True
            return False

        for _ in range(2):
            if not _check_hallucination(full_response):
                break
            if on_reset:
                await on_reset()
            messages.pop()
            messages.append({"role": "user", "content": f"用户要求：{message}\n\n请使用 [TOOL_CALL] 工具来执行文件操作，不要自行编造结果。"})
            full_response = ""
            async with httpx.AsyncClient(timeout=120.0) as client_h:
                resp_h = await client_h.post(
                    f"{MODEL_API_URL}/chat/completions",
                    headers=headers,
                    json={
                        "model": MODEL_NAME,
                        "messages": messages,
                        "stream": True,
                        "temperature": llm_config.get("temperature", 0.7),
                        "max_tokens": llm_config.get("max_tokens", 2048),
                    },
                )
                async for line in resp_h.aiter_lines():
                    if line.startswith("data: "):
                        ds = line[6:]
                        if ds == "[DONE]":
                            break
                        try:
                            d = json.loads(ds)
                            c = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if c:
                                full_response += c
                                await on_chunk(c)
                        except json.JSONDecodeError:
                            continue

        max_tool_rounds = 5
        tool_round = 0

        while True:
            tool_match = re.search(r'\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)', full_response, re.DOTALL)
            if not tool_match:
                break
            raw_call = tool_match.group(1).strip()
            if not raw_call:
                break

            # built-in tools
            tool_result = None
            try:
                call_data = json.loads(raw_call)
                tool_name = call_data.get("tool", "")
                params = call_data.get("params", {})
                if tool_name == "remember_global":
                    try:
                        from skills.memory_skill import remember_global
                        tool_result = remember_global(params.get("content",""), params.get("tags",""))
                    except Exception:
                        tool_result = "❌ 保存全局记忆失败"
                elif tool_name == "forget_global":
                    try:
                        from skills.memory_skill import forget_global
                        tool_result = forget_global(params.get("content",""))
                    except Exception:
                        tool_result = "❌ 删除记忆失败"
            except json.JSONDecodeError:
                pass

            if not tool_result:
                tool_result = await skill_engine.execute_tool_call(full_response, {"session_id": session_id, "on_chunk": on_chunk})
            if not tool_result:
                break

            tool_round += 1

            if on_reset:
                await on_reset()

            if tool_result.startswith("❌") or tool_result.startswith("📂") or tool_result.startswith("✅") or tool_result.startswith("📄") or tool_result.startswith("🗑️") or tool_result.startswith("╔══") or tool_result.startswith("🎵") or tool_result.startswith("⏹️") or tool_result.startswith("▶️") or "[IMG]" in tool_result or "[AUDIO]" in tool_result or "[AUDIO_STOP]" in tool_result or "[VIDEO]" in tool_result or "[VIDEO_STOP]" in tool_result:
                full_response = tool_result
                await on_chunk(tool_result)
                break

            char_mgr.reload_current()
            new_system = char_mgr.build_system_prompt(memory_summary)
            tools_prompt = skill_engine.get_tools_prompt()
            if tools_prompt:
                new_system += "\n\n" + tools_prompt
            messages[0] = {"role": "system", "content": new_system}

            messages.pop()  # remove original user message
            assistant_part = re.sub(r'\s*\[TOOL_CALL\].*?(?:\[/TOOL_CALL\]|$)\s*', '', full_response, flags=re.DOTALL).strip()
            messages.append({"role": "assistant", "content": assistant_part or "正在处理..."})
            messages.append({"role": "user", "content": f"工具已执行完成，结果如下：\n{tool_result}\n\n请直接用中文回复用户，把结果整理成易读的格式。不要调用任何工具。"})

            formatted = ""
            async with httpx.AsyncClient(timeout=120.0) as client_n:
                resp_n = await client_n.post(
                    f"{MODEL_API_URL}/chat/completions",
                    headers=headers,
                    json={
                        "model": MODEL_NAME,
                        "messages": messages,
                        "stream": True,
                        "temperature": llm_config.get("temperature", 0.7),
                        "max_tokens": llm_config.get("max_tokens", 2048),
                    },
                )
                async for line in resp_n.aiter_lines():
                    if line.startswith("data: "):
                        ds = line[6:]
                        if ds == "[DONE]":
                            break
                        try:
                            d = json.loads(ds)
                            c = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if c:
                                formatted += c
                                await on_chunk(c)
                        except json.JSONDecodeError:
                            continue
            full_response = formatted

            if tool_round >= max_tool_rounds:
                break

        mem_mgr.add_assistant_message(session_id, full_response)
        mem_mgr.save_all()

        asyncio.ensure_future(extract_key_points(session_id, message, full_response))

    except httpx.ConnectError:
        await on_chunk(
            f"\n\n⚠️ 无法连接到模型服务：{MODEL_API_URL}\n请确保模型服务正在运行。"
        )
    except Exception as e:
        from traceback import format_exc
        await on_chunk(f"\n\n⚠️ 错误：{e}")
        print(format_exc())


@app.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    init_feishu()
    body = await request.json()

    if "challenge" in body:
        return JSONResponse({"challenge": body["challenge"]})

    event = body.get("event", {})
    header = body.get("header", {})

    open_id = (event.get("sender", {}).get("sender_id", {}).get("open_id", "")
               or event.get("sender", {}).get("open_id", ""))
    event_type = (header.get("event_type", "")
                  or event.get("event_type", "")
                  or body.get("event_type", ""))
    msg_content = event.get("message", {}).get("content", "")
    try:
        msg_text = json.loads(msg_content).get("text", msg_content) if msg_content else ""
    except Exception:
        msg_text = msg_content

    if open_id and msg_text:
        logger.info("")
        logger.info("=" * 60)
        logger.info("收到飞书消息 来自=%s 内容=%s", open_id, msg_text[:200])
        logger.info("=" * 60)
        logger.info("")

    if not feishu_bot or not feishu_bot.enabled:
        logger.info("webhook未启用 event_type=%s", event_type)
        return JSONResponse({"msg": "feishu not enabled"})

    result = await feishu_bot.handle_webhook(body)
    return JSONResponse(result)


@app.post("/feishu/event")
async def feishu_event(request: Request):
    """兼容 schema 1.0 的事件回调（同 Flask 示例）"""
    init_feishu()
    data = await request.json()
    if "challenge" in data:
        return JSONResponse({"challenge": data["challenge"]})
    event = data.get("event", {})
    if event.get("type") == "message":
        sender_open_id = event.get("sender", {}).get("open_id", "")
        if sender_open_id:
            logger.info("")
            logger.info("=" * 60)
            logger.info("收到飞书消息 OPEN_ID=%s", sender_open_id)
            logger.info("=" * 60)
            logger.info("")
    return JSONResponse({"code": 0})


@app.get("/api/feishu/log")
async def api_feishu_log(lines: int = 50):
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu.log")
    if not os.path.exists(log_file):
        return {"success": True, "lines": []}
    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.read().splitlines()
    return {"success": True, "lines": all_lines[-lines:]}


@app.post("/feishu/test")
async def feishu_test(request: Request):
    init_feishu()
    if not feishu_bot or not feishu_bot.enabled:
        return JSONResponse({"ok": False, "msg": "飞书未启用，请在设置中配置"})
    token_ok = await feishu_bot.check_connection()
    return JSONResponse({
        "ok": token_ok,
        "msg": "token获取成功" if token_ok else "token获取失败，检查 app_id 和 app_secret 是否正确",
    })


@app.get("/api/feishu/test-token")
async def api_feishu_test_token():
    init_feishu()
    if not feishu_bot or not feishu_bot.app_id:
        return {"success": False, "error": "请先配置 app_id 和 app_secret"}
    try:
        token = await feishu_bot._get_token()
        if token:
            return {"success": True, "token": "***" + token[-6:], "expire_time": feishu_bot._token_expire}
        else:
            return {"success": False, "error": "获取Token失败，请检查 app_id 和 app_secret"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/feishu/test-message")
async def api_feishu_test_message(params: dict = None):
    init_feishu()
    if not feishu_bot or not feishu_bot.app_id:
        return {"success": False, "error": "请先配置 app_id 和 app_secret"}
    if params is None:
        params = {}
    result = await feishu_bot.send_test_message(
        text=params.get("text"), receive_id=params.get("receiveId"),
        receive_id_type=params.get("receiveIdType"),
    )
    return result


@app.get("/api/feishu/config-info")
async def api_feishu_config_info():
    init_feishu()
    if not feishu_bot:
        return {"success": False, "error": "飞书未初始化"}
    return {"success": True, "data": feishu_bot.get_config_info()}


@app.post("/api/feishu/lookup-user")
async def api_feishu_lookup_user(params: dict = None):
    init_feishu()
    if not feishu_bot or not feishu_bot.app_id:
        return {"success": False, "error": "请先配置 app_id 和 app_secret"}
    if params is None:
        params = {}
    email = params.get("email", "").strip()
    mobile = params.get("mobile", "").strip()
    if not email and not mobile:
        return {"success": False, "error": "请输入邮箱或手机号"}
    result = await feishu_bot.lookup_user(email=email or None, mobile=mobile or None)
    return result


@app.get("/api/music/play")
async def music_play(request: Request):
    path = request.query_params.get("path", "")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "file not found"}, status_code=404)
    ext = os.path.splitext(path)[1].lower()
    mime = {
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
        ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".aac": "audio/aac",
        ".wma": "audio/x-ms-wma", ".ape": "audio/x-ape", ".opus": "audio/ogg",
    }.get(ext, "audio/mpeg")
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type=mime, filename=os.path.basename(path),
                        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"})


@app.get("/api/video/play")
async def video_play(request: Request):
    path = request.query_params.get("path", "")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "file not found"}, status_code=404)
    ext = os.path.splitext(path)[1].lower()
    from fastapi.responses import FileResponse, StreamingResponse
    mime = {
        ".mp4": "video/mp4", ".webm": "video/webm", ".ogg": "video/ogg",
        ".avi": "video/x-msvideo", ".wmv": "video/x-ms-wmv", ".flv": "video/x-flv",
        ".mov": "video/quicktime", ".m4v": "video/mp4",
    }.get(ext, "application/octet-stream")
    file_size = os.path.getsize(path)
    range_header = request.headers.get("range")

    # MKV often has AC3/DTS audio unsupported in browsers -- transcode audio to AAC on the fly via ffmpeg
    if ext == ".mkv":
        cmd = ["ffmpeg", "-i", path, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)

        async def ffmpeg_stream():
            try:
                while True:
                    chunk = await process.stdout.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if process.returncode is None:
                    process.kill()
                await process.wait()
        return StreamingResponse(ffmpeg_stream(), media_type="video/mp4",
                                 headers={"Cache-Control": "no-cache",
                                          "Content-Disposition": "inline"})

    if range_header:
        start_str = range_header.replace("bytes=", "").split("-")[0]
        start = int(start_str) if start_str.isdigit() else 0
        end = min(start + 1024 * 1024, file_size - 1)
        if start >= file_size:
            return JSONResponse(status_code=416)
        async def ranged_stream():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        return StreamingResponse(ranged_stream(), status_code=206, media_type=mime, headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(end - start + 1), "Accept-Ranges": "bytes",
            "Content-Disposition": "inline"})
    return FileResponse(path, media_type=mime, filename=os.path.basename(path),
                        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache", "Content-Disposition": "inline"})


@app.get("/api/debug/character/{name}")
async def api_debug_character(name: str):
    profile = char_mgr.get_profile(name)
    chars = char_mgr.list_characters()
    file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "characters", f"{name}.json"
    )
    file_exists = os.path.exists(file_path)
    disk_content = None
    if file_exists:
        with open(file_path, "r", encoding="utf-8") as f:
            disk_content = json.load(f)
    return {
        "current_name": char_mgr.get_current_name(),
        "profiles_keys": list(char_mgr.profiles.keys()),
        "characters_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters"),
        "requested_profile_in_memory": profile,
        "file_path": file_path,
        "file_exists": file_exists,
        "disk_content": disk_content,
        "character_list": chars,
    }


@app.get("/api/debug/save_test")
async def api_debug_save_test():
    from datetime import datetime
    test_profile = {
        "name": "debug_test",
        "identity": "Debug test save at " + datetime.now().strftime("%H:%M:%S"),
        "traits": ["test"],
        "rules": [],
        "knowledge": [],
    }
    ok = char_mgr.save_profile("debug_test_char", test_profile)
    after = char_mgr.get_profile("debug_test_char")
    return {
        "save_result": ok,
        "after_memory": after,
        "characters_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters"),
    }


@app.get("/api/status")
async def api_status():
    ws_alive = _feishu_ws_thread is not None and _feishu_ws_thread.is_alive() if feishu_bot else False
    return {
        "status": "running",
        "model": MODEL_NAME,
        "model_api": MODEL_API_URL,
        "character": char_mgr.get_current_name(),
        "skills": len(skill_engine.skills),
        "feishu_enabled": feishu_bot.enabled if feishu_bot else False,
        "feishu_ws": ws_alive,
    }


@app.on_event("startup")
async def on_startup():
    _start_stt_server()
    init_feishu()
    await start_feishu_ws()
    from config import get_relay_config
    rc = get_relay_config()
    if rc.get("enabled") and rc.get("auto_connect"):
        from relay_client import get_relay as _get_relay, ensure_connected
        ok = await ensure_connected()
        print(f"[Relay] {'Connected' if ok else 'Connect failed'} to {rc.get('server_url', '')}")
        if ok:
            _relay = _get_relay()

            async def _relay_msg_handler(session_id, msg, reply, send_done):
                """Process incoming relay messages through LLM pipeline."""
                _audio_dir = os.path.join(os.path.dirname(__file__), "public", "audio")

                async def _on_chunk(chunk):
                    # Intercept [AUDIO] tags — read file and send base64
                    audio_match = re.search(r'\[AUDIO\](/static/audio/[^[]+)\[/AUDIO\]', chunk)
                    if audio_match:
                        rel_path = audio_match.group(1).lstrip("/static/")
                        file_path = os.path.join(os.path.dirname(__file__), rel_path.replace("/", os.sep))
                        if os.path.exists(file_path):
                            import base64
                            with open(file_path, "rb") as f:
                                b64 = base64.b64encode(f.read()).decode()
                            chunk = chunk.replace(audio_match.group(0), "")
                            if chunk.strip():
                                await reply(chunk)
                            await reply(f'[AUDIO_BASE64]{b64}[/AUDIO_BASE64]')
                            return
                    await reply(chunk)

                async def _on_reset():
                    pass

                await send_to_llm(msg, session_id, _on_chunk, source="relay", on_reset=_on_reset)
                await send_done()

            _relay.set_message_handler(_relay_msg_handler)
            print("[Relay] Message handler registered")

            async def _relay_auto_reconnect():
                await _relay.auto_reconnect()

            asyncio.create_task(_relay_auto_reconnect())


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", get_server_config().get("port", 8000)))
    print("\n启动服务器: http://localhost:%d/" % port)
    uvicorn.run(app, host="0.0.0.0", port=port)
