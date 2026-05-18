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

## 微信自动化功能

### 使用方式

在聊天窗口中输入命令：

```
/wechat "文件传输助手" "你好"
/wechat "张三" "在吗？"
/wechat "群聊名称" "大家好"
```

### 命令格式

```
/wechat "联系人或群组名称" "要发送的消息"
```

### 示例

1. **给文件传输助手发送消息：**
   ```
   /wechat "文件传输助手" "你好"
   ```

2. **给特定联系人发送消息：**
   ```
   /wechat "张三" "明天见！"
   ```

3. **在群聊中发送消息：**
   ```
   /wechat "工作群" "会议通知"
   ```

### 注意事项

- ⚠️ 需要手动启动微信并切换到微信窗口
- 📱 首次运行需要观察搜索结果的准确位置
- ⏱️ 可根据电脑性能调整 `wechat_auto.py` 中的延迟配置
- 🖱️ 将鼠标移到屏幕角落可随时中断程序

### 配置调整

如果点击位置不准确，调整 `wechat_auto.py` 中的配置：

```python
CONFIG = {
    "wait_after_search": 1.5,  # 搜索后等待时间（秒）
    "enter_chat_delay": 1.5,   # 进入聊天等待时间（秒）
}

CHAT_ITEM_OFFSET = 100  # 聊天列表项的垂直偏移
CHAT_ITEM_HEIGHT = 50   # 每个聊天项的高度
```
