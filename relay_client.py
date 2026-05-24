"""WebSocket relay client — connects to relay server as role=agent."""
import asyncio
import json
import uuid
from typing import Optional, Callable
from websockets.asyncio.client import connect

from config import get_relay_config


class RelayClient:
    def __init__(self):
        self.ws = None
        self._connected = False
        self._pending: dict[str, asyncio.Future] = {}
        self._on_message: Optional[Callable] = None

    @property
    def connected(self):
        return self._connected

    def set_message_handler(self, handler: Callable):
        """handler(session_id, message, reply_func) where reply_func(chunk) sends back chunks."""
        self._on_message = handler

    async def connect(self):
        cfg = get_relay_config()
        url = cfg.get("server_url", "")
        if not url:
            return
        token = cfg.get("token", "")
        try:
            uri = f"{url}?role=agent&token={token}" if token else f"{url}?role=agent"
            self.ws = await connect(uri, max_size=100 * 1024 * 1024)
            self._connected = True
            print(f"[Relay] Connected to {url}")
            asyncio.create_task(self._listen())
        except Exception as e:
            print(f"[Relay] Connect failed: {e}")
            self._connected = False

    async def disconnect(self):
        self._connected = False
        if self.ws:
            await self.ws.close()

    async def _listen(self):
        try:
            async for msg in self.ws:
                if isinstance(msg, bytes):
                    continue
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                # Response to a pending command request
                rid = data.get("id")
                if rid and rid in self._pending:
                    fut = self._pending.pop(rid)
                    if not fut.done():
                        fut.set_result(data)
                    continue

                # Incoming chat message from app (via relay)
                if data.get("type") == "chat" and self._on_message:
                    session_id = data.get("session_id", "relay_default")
                    user_msg = data.get("message", "")

                    async def send_chunk(chunk: str):
                        if self.ws and self._connected:
                            try:
                                await self.ws.send(json.dumps({
                                    "type": "chunk", "content": chunk,
                                    "session_id": session_id,
                                }, ensure_ascii=False))
                            except Exception:
                                pass

                    async def send_done():
                        if self.ws and self._connected:
                            try:
                                await self.ws.send(json.dumps({
                                    "type": "done", "session_id": session_id,
                                }))
                            except Exception:
                                pass

                    async def reply(chunk: str):
                        await send_chunk(chunk)

                    asyncio.create_task(self._on_message(session_id, user_msg, reply, send_done))
        except Exception as e:
            print(f"[Relay] Listen error: {e}")
        finally:
            self._connected = False

    async def send_raw(self, payload: dict):
        if self._connected and self.ws:
            await self.ws.send(json.dumps(payload, ensure_ascii=False))

    async def send_request(self, tool: str, params: dict, timeout: float = 60.0) -> dict:
        if not self._connected:
            return {"error": "not connected"}
        rid = str(uuid.uuid4())
        fut = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        try:
            await self.ws.send(json.dumps({
                "type": "command", "id": rid, "tool": tool, "params": params,
            }, ensure_ascii=False))
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            return {"error": "timeout"}
        except Exception as e:
            self._pending.pop(rid, None)
            return {"error": str(e)}


_relay = RelayClient()


def get_relay():
    return _relay


async def ensure_connected():
    if not _relay.connected:
        await _relay.connect()
    return _relay.connected
