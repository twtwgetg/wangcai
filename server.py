import os
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from typing import Dict, List
import json

app = FastAPI(title="本地 LLM 智能体")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="public"), name="static")

# 模型服务配置
MODEL_API_URL = os.environ.get("MODEL_API_URL", "http://127.0.0.1:8080/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-2-7b-chat")

# 对话存储
conversations: Dict[str, List[dict]] = {}

print(f"📡 模型服务地址：{MODEL_API_URL}")
print(f"📦 模型名称：{MODEL_NAME}")


@app.get("/")
async def root():
    """返回聊天页面"""
    from fastapi.responses import HTMLResponse

    with open("public/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 聊天接口"""
    await websocket.accept()
    client_id = id(websocket)
    session_id = f"session_{client_id}"

    print(f"客户端连接：{client_id}")

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            session_id = message_data.get("session_id", session_id)

            print(f"收到消息：{user_message[:50]}...")

            # 响应处理
            async def handle_chunk(chunk):
                await websocket.send_json({"type": "chunk", "content": chunk})

            # 发送消息给 LLM
            await send_to_llm(user_message, session_id, handle_chunk)

            # 完成消息
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print(f"客户端断开：{client_id}")
    except Exception as e:
        print(f"错误：{e}")
        await websocket.send_json({"type": "error", "message": str(e)})


async def send_to_llm(message: str, session_id: str, on_chunk):
    """通过 HTTP API 发送消息给 LLM 并流式返回响应"""

    # 系统提示词
    system_prompt = """You are a helpful AI assistant. Provide detailed, thoughtful responses to the user's questions."""

    # 获取对话历史
    if session_id not in conversations:
        conversations[session_id] = []

    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversations[session_id][-20:])  # 保留最近 20 条
    messages.append({"role": "user", "content": message})

    # 生成响应
    full_response = ""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{MODEL_API_URL}/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            )

            # 读取流式响应
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

        # 保存对话
        conversations[session_id].append({"role": "user", "content": message})
        conversations[session_id].append(
            {"role": "assistant", "content": full_response}
        )

    except httpx.ConnectError:
        await on_chunk(
            f"\n\n⚠️ 无法连接到模型服务：{MODEL_API_URL}\n请确保 llama-server 或其他兼容服务正在运行。"
        )
    except Exception as e:
        await on_chunk(f"\n\n⚠️ 错误：{e}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"\n🚀 启动服务器：http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
