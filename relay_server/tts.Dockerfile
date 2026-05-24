FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir edge-tts fastapi uvicorn[standard]
COPY tts_server.py ./
EXPOSE 9526
CMD ["uvicorn", "tts_server:app", "--host", "0.0.0.0", "--port", "9526"]