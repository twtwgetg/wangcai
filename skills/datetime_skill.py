from datetime import datetime
from skill import BaseSkill


class DateTimeSkill(BaseSkill):
    name = "时间日期"
    description = "获取当前日期和时间"
    triggers = ["现在几点", "现在时间", "今天几号", "当前时间", "日期", "date", "time"]

    async def execute(self, message, context=None):
        msg_lower = message.lower()
        if not any(t in msg_lower for t in self.triggers):
            return None
        now = datetime.now()
        return f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"
