package com.wangcai.app

import android.os.Handler
import android.os.Looper
import com.google.gson.Gson
import com.google.gson.JsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

class WangcaiClient(
    private val onConnected: () -> Unit,
    private val onDisconnected: () -> Unit,
    private val onChunk: (String) -> Unit,
    private val onDone: () -> Unit,
    private val onError: (String) -> Unit
) {
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .connectTimeout(10, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val gson = Gson()
    private val handler = Handler(Looper.getMainLooper())

    fun connect(url: String) {
        disconnect()
        val request = Request.Builder().url(url).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                handler.post { onConnected() }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                handler.post { onDisconnected() }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                handler.post { onDisconnected() }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                handler.post { onError(t.message ?: "连接失败") }
                handler.post { onDisconnected() }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = gson.fromJson(text, JsonObject::class.java)
                    val type = json.get("type")?.asString ?: return

                    when (type) {
                        "chunk" -> {
                            val content = json.get("content")?.asString ?: ""
                            handler.post { onChunk(content) }
                        }
                        "done" -> handler.post { onDone() }
                        "error" -> {
                            val msg = json.get("message")?.asString ?: "未知错误"
                            handler.post { onError(msg) }
                        }
                    }
                } catch (e: Exception) {
                    handler.post { onError("解析消息失败: ${e.message}") }
                }
            }
        })
    }

    fun sendMessage(message: String) {
        val json = JsonObject().apply {
            addProperty("type", "chat")
            addProperty("message", message)
            addProperty("session_id", "android_${System.currentTimeMillis()}")
        }
        webSocket?.send(gson.toJson(json))
    }

    fun disconnect() {
        webSocket?.close(1000, "用户断开")
        webSocket = null
    }
}
