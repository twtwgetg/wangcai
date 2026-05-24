"""轻量 TTS API 服务 - 基于 edge-tts，支持流式输出"""
import asyncio
import io
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

app = FastAPI(title="TTS API")


@app.get("/tts")
async def text_to_speech(text: str = Query(..., description="要朗读的文字"),
                         voice: str = Query("zh-CN-XiaoxiaoNeural", description="语音角色")):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)

    async def audio_stream():
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                if buffer.tell() > 0:
                    yield buffer.getvalue()
                    buffer = io.BytesIO()
        if buffer.tell() > 0:
            yield buffer.getvalue()

    return StreamingResponse(audio_stream(), media_type="audio/mpeg",
                             headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9526)
