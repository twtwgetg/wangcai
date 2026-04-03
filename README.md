# 本地 LLM 智能体聊天系统

## 架构说明

```
┌─────────────┐      HTTP API      ┌──────────────────┐
│   浏览器     │◄───────WebSocket──►│   FastAPI 服务    │
│  (聊天界面)  │      /ws           │   (server.py)    │
└─────────────┘                    └────────┬─────────┘
                                           │
                                   HTTP POST
                                    /v1/
                                           ▼
                                  ┌──────────────────┐
                                  │  模型服务         │
                                  │ (llama-server 等) │
                                  │  :8080           │
                                  └──────────────────┘
```

## 前提条件

需要运行一个支持 OpenAI API 格式的本地模型服务：

### 选项 1: llama-server (llama.cpp)
```bash
./server -m models/llama-2-7b-chat.gguf -c 4096 --port 8080
```

### 选项 2: Ollama
```bash
ollama serve
# 然后访问 http://127.0.0.1:11434/v1
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行聊天服务

```bash
# 默认配置 (llama-server @ 8080)
python server.py

# 自定义模型服务地址
MODEL_API_URL=http://127.0.0.1:11434/v1 python server.py

# 自定义模型名称
MODEL_NAME=llama2 python server.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL_API_URL` | `http://127.0.0.1:8080/v1` | 模型服务 API 地址 |
| `MODEL_NAME` | `llama-2-7b-chat` | 模型名称 |
| `PORT` | `8000` | 聊天服务端口 |

## 访问

打开浏览器访问：**http://localhost:8000**
