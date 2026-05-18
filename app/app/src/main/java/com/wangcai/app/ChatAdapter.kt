package com.wangcai.app

import android.view.Gravity
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.wangcai.app.databinding.ItemChatMessageBinding

class ChatAdapter : ListAdapter<ChatMessage, ChatAdapter.ViewHolder>(DiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemChatMessageBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class ViewHolder(private val binding: ItemChatMessageBinding) :
        RecyclerView.ViewHolder(binding.root) {

        fun bind(message: ChatMessage) {
            binding.messageText.text = message.text

            val params = binding.messageContainer.layoutParams as ViewGroup.MarginLayoutParams

            if (message.isUser) {
                params.marginStart = 100
                params.marginEnd = 0
                binding.messageContainer.gravity = Gravity.END
                binding.bubbleCard.setCardBackgroundColor(
                    ContextCompat.getColor(binding.root.context, R.color.user_bubble)
                )
                binding.messageText.setTextColor(
                    ContextCompat.getColor(binding.root.context, android.R.color.white)
                )
            } else {
                params.marginStart = 0
                params.marginEnd = 100
                binding.messageContainer.gravity = Gravity.START
                binding.bubbleCard.setCardBackgroundColor(
                    ContextCompat.getColor(binding.root.context, R.color.bot_bubble)
                )
                binding.messageText.setTextColor(
                    ContextCompat.getColor(binding.root.context, android.R.color.black)
                )
            }
            binding.messageContainer.layoutParams = params
        }
    }

    class DiffCallback : DiffUtil.ItemCallback<ChatMessage>() {
        override fun areItemsTheSame(oldItem: ChatMessage, newItem: ChatMessage): Boolean =
            oldItem === newItem

        override fun areContentsTheSame(oldItem: ChatMessage, newItem: ChatMessage): Boolean =
            oldItem.text == newItem.text && oldItem.isStreaming == newItem.isStreaming
    }
}
