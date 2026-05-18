import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

APP_ID = ""
APP_SECRET = ""

if not APP_ID or not APP_SECRET:
    try:
        with open("config.json", encoding="utf-8") as f:
            cfg = json.load(f).get("feishu", {})
            APP_ID = cfg.get("app_id", "")
            APP_SECRET = cfg.get("app_secret", "")
    except Exception:
        pass

port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        if "challenge" in body:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"challenge": body["challenge"]}).encode())
            return

        event = body.get("event", {})
        header = body.get("header", {})

        open_id = (event.get("sender", {}).get("sender_id", {}).get("open_id", "")
                   or event.get("sender", {}).get("open_id", ""))

        event_type = (header.get("event_type", "")
                      or event.get("event_type", "")
                      or body.get("event_type", ""))

        if event_type == "im.message.receive_v1" and open_id:
            print()
            print("=" * 60)
            print("  飞书消息发送者 OPEN_ID =", open_id)
            print("  请将此 ID 填入 config.json 的 feishu.receive_id")
            print("=" * 60)
            print()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"code": 0}).encode())

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}")


print(f"启动 webhook 服务: http://0.0.0.0:{port}/")
print(f"在飞书开放平台配置回调地址: http://你的公网IP:{port}/")
print("等待飞书事件...")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()
