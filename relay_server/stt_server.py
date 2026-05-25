"""轻量 STT API 服务 - 基于 faster-whisper/openai-whisper，GPU 加速"""
import io
import json
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="STT API")

_model = None

def get_model():
    global _model
    if _model is None:
        import whisper
        print("[STT] Loading medium model...", flush=True)
        _model = whisper.load_model("medium")
        print("[STT] Model loaded", flush=True)
    return _model


@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    model = get_model()
    try:
        content = await file.read()
        suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = model.transcribe(tmp_path, language="zh")
            text = result.get("text", "").strip()
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
        if not text:
            return JSONResponse({"text": "", "error": "no speech detected"}, status_code=400)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9528)
