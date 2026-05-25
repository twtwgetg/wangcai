@echo off
chcp 65001 >nul
echo Starting STT server (py310, GPU)...
start "STT" /B C:\Users\xuqua\miniconda3\envs\py310\python.exe -u D:\project\wangcai\relay_server\stt_server.py
timeout /t 15 /nobreak >nul
echo Starting main agent server...
C:\Users\xuqua\miniconda3\python.exe -u D:\project\wangcai\server.py
