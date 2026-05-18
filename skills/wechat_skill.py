import re
from skill import BaseSkill


class WeChatSkill(BaseSkill):
    name = "微信发送"
    description = "发送微信消息给联系人"
    triggers = ["发微信", "wechat", "微信"]

    async def execute(self, message, context=None):
        pattern = r"(?:发微信|wechat)\s+[\"']?([^\"']+)[\"']?\s+[\"']?(.+)[\"']?$"
        match = re.match(pattern, message.strip(), re.IGNORECASE)
        if match:
            contact = match.group(1).strip()
            msg = match.group(2).strip()
            from wechat_auto import search_and_chat
            try:
                result = search_and_chat(contact, msg, auto_find_window=True)
                if result and result.startswith("❌"):
                    return f"微信发送失败: {result}"
                return f"✅ 已给 '{contact}' 发送消息"
            except Exception as e:
                return f"微信发送出错: {e}"
        return None
