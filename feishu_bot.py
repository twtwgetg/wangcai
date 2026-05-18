import json
import time
import sys
import httpx
import logging
import os
import asyncio
import threading
import lark_oapi as lark
from config import get_feishu_config, load_config, save_config

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu.log")
logger = logging.getLogger("feishu")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("[feishu] %(message)s"))
    logger.addHandler(sh)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuBot:
    def __init__(self, message_handler=None):
        self.config = get_feishu_config()
        self.enabled = self.config.get("enabled", False)
        self.app_id = self.config.get("app_id", "")
        self.app_secret = self.config.get("app_secret", "")
        self.bot_name = self.config.get("bot_name", "旺财")
        self.receive_id = self.config.get("receive_id", "")
        self.receive_id_type = self.config.get("receive_id_type", "open_id")
        self.message_handler = message_handler
        self._token = None
        self._token_expire = 0
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=10.0, read=10.0, write=10.0))

    async def _get_token(self):
        if self._token and time.time() < self._token_expire:
            return self._token
        if not self.app_id or not self.app_secret:
            return None
        try:
            resp = await self._http.post(
                f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            if not resp.is_success:
                logger.error(f"获取飞书Token失败: HTTP {resp.status_code} {resp.text[:200]}")
                return None

            data = resp.json()
            code = data.get("code", -1)
            if code != 0:
                logger.error(f"获取飞书Token失败: {data.get('msg', 'unknown')}")
                return None

            self._token = data.get("tenant_access_token")
            expire = data.get("expire", 7200)
            self._token_expire = time.time() + (expire - 300)
            return self._token
        except Exception as e:
            logger.error(f"获取飞书Token异常: {e}")
            return None

    async def check_connection(self):
        token = await self._get_token()
        return token is not None

    async def send_message(self, open_id: str, text: str, receive_id_type: str = "open_id"):
        token = await self._get_token()
        if not token:
            return {"success": False, "error": "无法获取飞书Token"}
        try:
            content = json.dumps({"text": text}, ensure_ascii=False)
            resp = await self._http.post(
                f"{FEISHU_BASE}/im/v1/messages?receive_id_type={receive_id_type}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"receive_id": open_id, "msg_type": "text", "content": content},
            )
            body = resp.json()
            if resp.is_success:
                return {"success": True, "data": body}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {body.get('msg', resp.text[:200])}"}
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return {"success": False, "error": str(e)}

    async def send_test_message(self, text: str = None, receive_id: str = None, receive_id_type: str = None):
        text = text or f"测试消息 - {int(time.time())}"
        receive_id = receive_id or self.receive_id
        receive_id_type = receive_id_type or self.receive_id_type

        if not receive_id:
            return {"success": False, "error": "未配置 receive_id，请在飞书设置中填写"}

        token = await self._get_token()
        if not token:
            return {"success": False, "error": "无法获取飞书Token，请检查 app_id 和 app_secret"}

        try:
            content = json.dumps({"text": text}, ensure_ascii=False)
            resp = await self._http.post(
                f"{FEISHU_BASE}/im/v1/messages?receive_id_type={receive_id_type}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"receive_id": receive_id, "msg_type": "text", "content": content},
            )
            body = resp.json()
            return {
                "success": resp.is_success,
                "response_code": resp.status_code,
                "response": body,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_config_info(self):
        return {
            "app_id": (self.app_id[:4] + "****" + self.app_id[-4:]) if len(self.app_id) > 8 else "***",
            "app_secret": bool(self.app_secret),
            "receive_id": self.receive_id,
            "receive_id_type": self.receive_id_type,
            "bot_name": self.bot_name,
            "enabled": self.enabled,
        }

    def update_config(self, enabled=None, app_id=None, app_secret=None, receive_id=None, receive_id_type=None, bot_name=None):
        if enabled is not None:
            self.enabled = enabled
        if app_id is not None and app_id and "****" not in app_id:
            self.app_id = app_id
        if app_secret is not None and app_secret and "****" not in app_secret:
            self.app_secret = app_secret
        if receive_id is not None:
            self.receive_id = receive_id
        if receive_id_type is not None:
            self.receive_id_type = receive_id_type
        if bot_name is not None:
            self.bot_name = bot_name
        self._token = None

        cfg = load_config()
        feishu_cfg = cfg.setdefault("feishu", {})
        feishu_cfg["enabled"] = self.enabled
        feishu_cfg["app_id"] = self.app_id
        feishu_cfg["app_secret"] = self.app_secret
        feishu_cfg["receive_id"] = self.receive_id
        feishu_cfg["receive_id_type"] = self.receive_id_type
        feishu_cfg["bot_name"] = self.bot_name
        save_config(cfg)

    async def lookup_user(self, email: str = None, mobile: str = None):
        """通过邮箱或手机号查询飞书用户的 open_id"""
        token = await self._get_token()
        if not token:
            return {"success": False, "error": "无法获取飞书Token"}

        body = {}
        if email:
            body["emails"] = [email]
        if mobile:
            body["mobiles"] = [mobile]

        try:
            resp = await self._http.post(
                f"{FEISHU_BASE}/contact/v3/users/batch_get_id",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
            data = resp.json()
            code = data.get("code", -1)
            if code != 0:
                return {"success": False, "error": data.get("msg", "查询失败")}
            users = data.get("data", {}).get("user_list", [])
            if not users:
                return {"success": False, "error": "未找到对应用户"}
            u = users[0]
            return {
                "success": True,
                "open_id": u.get("open_id", ""),
                "user_id": u.get("user_id", ""),
                "name": u.get("name", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def start_ws_listener(self):
        """通过飞书官方 SDK 建立长连接（无需公网）"""
        if not self.app_id or not self.app_secret:
            logger.error("WS 未配置 app_id/app_secret")
            return

        main_loop = asyncio.get_event_loop()

        def on_message(data: lark.im.v1.P2ImMessageReceiveV1):
            event = data.event
            if not event:
                return
            sender_id = event.sender.sender_id.open_id if event.sender and event.sender.sender_id else ""
            message = event.message
            content_str = message.content if message else ""
            msg_type = message.message_type if message else ""
            try:
                text = json.loads(content_str).get("text", content_str)
            except Exception:
                text = content_str
            if msg_type == "text" and sender_id and text:
                logger.info("收到飞书消息: %s (from=%s)", text[:100], sender_id)
                coro = self._handle_incoming(sender_id, text)
                asyncio.run_coroutine_threadsafe(coro, main_loop)

        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(on_message) \
            .build()

        def run_ws():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            import lark_oapi.ws.client as ws_client
            old_loop = ws_client.loop
            ws_client.loop = new_loop
            try:
                cli = lark.ws.Client(
                    self.app_id, self.app_secret,
                    event_handler=event_handler,
                    log_level=lark.LogLevel.ERROR,
                )
                logger.info("WS 启动连接飞书事件服务...")
                cli.start()
            except Exception as e:
                logger.error("WS 连接异常: %s", e)
            finally:
                ws_client.loop = old_loop

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()
        logger.info("WS 监听线程已启动")

    async def _handle_incoming(self, sender_id: str, text: str):
        if self.message_handler:
            response = await self.message_handler(
                session_id=f"feishu_{sender_id}",
                message=text,
                source="feishu",
            )
            if response:
                result = await self.send_message(sender_id, response)
                if not result.get("success"):
                    logger.error("回复失败: %s", result.get("error"))

    def verify_webhook(self, body: dict) -> bool:
        return self.enabled

    async def handle_webhook(self, body: dict):
        if "challenge" in body:
            return {"challenge": body["challenge"]}

        if not self.enabled:
            return {"msg": "feishu not enabled"}

        event = body.get("event", {})
        header = body.get("header", {})

        event_type = (header.get("event_type", "")
                      or event.get("event_type", "")
                      or body.get("event_type", "")
                      or event.get("type", ""))
        is_message = event_type in ("im.message.receive_v1", "message")

        msg_type = (event.get("message", {}).get("message_type", "")
                    or event.get("msg_type", ""))
        content_str = (event.get("message", {}).get("content", "")
                       or event.get("content", ""))

        sender = event.get("sender", {})
        sender_id = (sender.get("sender_id", {}).get("open_id", "")
                     or sender.get("open_id", "")
                     or event.get("open_id", ""))

        if is_message and msg_type == "text" and sender_id:
            try:
                text = json.loads(content_str).get("text", content_str)
            except json.JSONDecodeError:
                text = content_str

            logger.info("收到飞书消息: %s (from=%s)", text[:100], sender_id)

            if self.message_handler:
                response = await self.message_handler(
                    session_id=f"feishu_{sender_id}",
                    message=text,
                    source="feishu",
                )
                if response:
                    result = await self.send_message(sender_id, response)
                    if not result.get("success"):
                        logger.error("回复失败: %s", result.get("error"))

        return {"msg": "ok"}
