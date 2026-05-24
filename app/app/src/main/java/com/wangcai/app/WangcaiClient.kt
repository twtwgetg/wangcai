package com.wangcai.app

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import android.util.Base64
import com.google.gson.Gson
import com.google.gson.JsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
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

    private var mediaPlayer: MediaPlayer? = null
    private var useRelay = false
    private var audioBuffer = ByteArrayOutputStream()

    // ---- Connection ----

    fun connectDirect(url: String) {
        useRelay = false
        disconnect()
        val req = Request.Builder().url(url).build()
        webSocket = client.newWebSocket(req, directListener)
    }

    fun connectRelay(relayUrl: String) {
        useRelay = true
        disconnect()
        val req = Request.Builder().url(relayUrl).build()
        webSocket = client.newWebSocket(req, relayListener)
    }

    fun sendMessage(text: String) {
        if (useRelay) {
            webSocket?.send(text)
        } else {
            val json = JsonObject().apply {
                addProperty("type", "chat")
                addProperty("message", text)
                addProperty("session_id", "android_${System.currentTimeMillis()}")
            }
            webSocket?.send(gson.toJson(json))
        }
    }

    fun disconnect() {
        stopAudio()
        webSocket?.close(1000, "disconnect")
        webSocket = null
    }

    // ---- Direct mode ----

    private val directListener = object : WebSocketListener() {
        override fun onOpen(ws: WebSocket, resp: Response) {
            handler.post { onConnected() }
        }

        override fun onClosing(ws: WebSocket, code: Int, reason: String) {
            ws.close(1000, null)
            handler.post { onDisconnected() }
        }

        override fun onClosed(ws: WebSocket, code: Int, reason: String) {
            handler.post { onDisconnected() }
        }

        override fun onFailure(ws: WebSocket, t: Throwable, resp: Response?) {
            handler.post { onError(t.message ?: "连接失败") }
            handler.post { onDisconnected() }
        }

        override fun onMessage(ws: WebSocket, text: String) {
            try {
                val json = gson.fromJson(text, JsonObject::class.java)
                when (json.get("type")?.asString) {
                    "chunk" -> handler.post { onChunk(json.get("content")?.asString ?: "") }
                    "done" -> handler.post { onDone() }
                    "error" -> handler.post { onError(json.get("message")?.asString ?: "未知错误") }
                }
            } catch (e: Exception) {
                handler.post { onError("解析失败: ${e.message}") }
            }
        }
    }

    // ---- Relay mode ----

    private val relayListener = object : WebSocketListener() {
        override fun onOpen(ws: WebSocket, resp: Response) {
            handler.post { onConnected() }
        }

        override fun onClosing(ws: WebSocket, code: Int, reason: String) {
            ws.close(1000, null)
            handler.post { onDisconnected() }
        }

        override fun onClosed(ws: WebSocket, code: Int, reason: String) {
            handler.post { onDisconnected() }
        }

        override fun onFailure(ws: WebSocket, t: Throwable, resp: Response?) {
            handler.post { onError(t.message ?: "连接失败") }
            handler.post { onDisconnected() }
        }

        override fun onMessage(ws: WebSocket, text: String) {
            try {
                val json = gson.fromJson(text, JsonObject::class.java)
                val type = json.get("type")?.asString ?: ""
                when (type) {
                    "connected" -> return
                    "chunk" -> handler.post { onChunk(json.get("content")?.asString ?: "") }
                    "done" -> handler.post { onDone() }
                    "error" -> handler.post { onError(json.get("message")?.asString ?: "未知错误") }
                    "audio_start" -> {
                        audioBuffer = ByteArrayOutputStream()
                        handler.post { onChunk("🎵 正在接收音频...\n") }
                    }
                    "audio_chunk" -> {
                        val b64 = json.get("data")?.asString ?: ""
                        if (b64.isNotEmpty()) {
                            audioBuffer.write(Base64.decode(b64, Base64.DEFAULT))
                        }
                    }
                    "audio_end" -> {
                        playBufferedAudio()
                    }
                }
            } catch (e: Exception) {
                handler.post { onError("解析失败: ${e.message}") }
            }
        }
    }

    private fun playBufferedAudio() {
        try {
            val audioData = audioBuffer.toByteArray()
            if (audioData.isEmpty()) return

            val tempFile = File.createTempFile("wangcai_", ".mp3")
            FileOutputStream(tempFile).use { it.write(audioData) }

            stopAudio()
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build())
                setOnCompletionListener {
                    handler.post { onChunk("🎵 播放完毕\n") }
                }
                setOnErrorListener { _, what, extra ->
                    handler.post { onError("音频错误: $what/$extra") }
                    true
                }
                setDataSource(tempFile.absolutePath)
                prepare()
                start()
            }
        } catch (e: Exception) {
            handler.post { onError("音频播放失败: ${e.message}") }
        }
    }

    private fun stopAudio() {
        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
        } catch (_: Exception) { }
        mediaPlayer = null
        audioBuffer = ByteArrayOutputStream()
    }
}
