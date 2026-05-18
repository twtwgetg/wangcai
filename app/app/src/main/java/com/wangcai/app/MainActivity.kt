package com.wangcai.app

import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.wangcai.app.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var adapter: ChatAdapter
    private val messages = mutableListOf<ChatMessage>()
    private var currentBotIndex = -1
    private var isConnected = false
    private var isReceiving = false

    private lateinit var client: WangcaiClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        adapter = ChatAdapter()
        binding.chatRecycler.layoutManager = LinearLayoutManager(this)
        binding.chatRecycler.adapter = adapter
        binding.chatRecycler.setHasFixedSize(false)

        client = WangcaiClient(
            onConnected = {
                isConnected = true
                binding.statusText.text = "已连接"
                binding.connectBtn.text = "断开"
                addBotMessage("已连接到服务器")
            },
            onDisconnected = {
                isConnected = false
                isReceiving = false
                binding.statusText.text = "未连接"
                binding.connectBtn.text = "连接"
            },
            onChunk = { chunk ->
                if (!isReceiving) {
                    isReceiving = true
                    currentBotIndex = messages.size
                    messages.add(ChatMessage(chunk, isUser = false, isStreaming = true))
                    adapter.submitList(messages.toList())
                } else {
                    val last = messages.lastOrNull()
                    if (last != null && last.isStreaming) {
                        messages[messages.size - 1] = last.copy(text = last.text + chunk)
                    } else {
                        currentBotIndex = messages.size
                        messages.add(ChatMessage(chunk, isUser = false, isStreaming = true))
                    }
                    adapter.submitList(messages.toList())
                }
                binding.chatRecycler.smoothScrollToPosition(adapter.itemCount - 1)
            },
            onDone = {
                isReceiving = false
                if (currentBotIndex >= 0 && currentBotIndex < messages.size) {
                    messages[currentBotIndex] = messages[currentBotIndex].copy(isStreaming = false)
                    adapter.submitList(messages.toList())
                }
            },
            onError = { error ->
                addBotMessage("⚠️ $error")
                isReceiving = false
            }
        )

        binding.connectBtn.setOnClickListener {
            if (isConnected) {
                client.disconnect()
            } else {
                connectToServer()
            }
        }

        binding.messageInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendMessage()
                true
            } else false
        }

        binding.sendBtn.setOnClickListener { sendMessage() }

        loadSavedUrl()
    }

    private fun connectToServer() {
        var url = binding.serverUrl.text.toString().trim()
        if (url.isEmpty()) {
            binding.statusText.text = "请输入服务器地址"
            return
        }
        if (!url.startsWith("ws://") && !url.startsWith("wss://")) {
            url = "ws://$url"
        }
        binding.statusText.text = "连接中..."
        binding.connectBtn.isEnabled = false
        getSharedPreferences("config", MODE_PRIVATE).edit()
            .putString("server_url", url).apply()
        client.connect(url)
        binding.connectBtn.isEnabled = true
    }

    private fun sendMessage() {
        val text = binding.messageInput.text.toString().trim()
        if (text.isEmpty() || !isConnected || isReceiving) return

        messages.add(ChatMessage(text, isUser = true))
        adapter.submitList(messages.toList())
        binding.chatRecycler.smoothScrollToPosition(adapter.itemCount - 1)
        binding.messageInput.text.clear()
        client.sendMessage(text)
    }

    private fun addBotMessage(text: String) {
        messages.add(ChatMessage(text, isUser = false))
        adapter.submitList(messages.toList())
        binding.chatRecycler.smoothScrollToPosition(adapter.itemCount - 1)
    }

    private fun loadSavedUrl() {
        val url = getSharedPreferences("config", MODE_PRIVATE)
            .getString("server_url", "") ?: ""
        if (url.isNotEmpty()) {
            binding.serverUrl.setText(url)
        }
    }

    override fun onDestroy() {
        client.disconnect()
        super.onDestroy()
    }
}
