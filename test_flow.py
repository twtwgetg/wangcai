import asyncio
import json
import websockets


async def test():
    async with websockets.connect("ws://localhost:9527/ws") as ws:
        msg = json.dumps({
            "type": "chat",
            "message": "搜索风景照片",
            "session_id": "final_img_test"
        })
        await ws.send(msg)
        while True:
            resp = await asyncio.wait_for(ws.recv(), timeout=120)
            data = json.loads(resp)
            if data["type"] == "done":
                break
            elif data["type"] == "chunk":
                text = data["content"].replace("[TOOL_CALL]", "\n<<<TOOL_CALL>>>").replace("[/TOOL_CALL]", "<<</TOOL_CALL>>>")
                print(text, end="", flush=True)
            elif data["type"] == "clear_stream":
                print("\n[CLEAR_STREAM]")
            elif data["type"] == "error":
                print(f"\n[ERROR] {data['message']}")
        print("\n=== DONE ===")

asyncio.run(test())
