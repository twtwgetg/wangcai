const WebSocket = require('ws');
const http = require('http');
const url = require('url');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = process.env.PORT || 8080;
const TOKEN = process.env.RELAY_TOKEN || '';

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/chat') {
    const chatPath = path.join(__dirname, 'chat.html');
    fs.readFile(chatPath, (err, data) => {
      if (err) {
        res.writeHead(500);
        res.end('Internal error');
        return;
      }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(data);
    });
    return;
  }
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('Wangcai Relay Server\n');
});

const wss = new WebSocket.Server({ server });

const connections = new Map(); // id -> {ws, role, metadata}

function genId() {
  return crypto.randomUUID();
}

function getClients(role) {
  const result = [];
  for (const [, c] of connections) {
    if (c.role === role && c.ws.readyState === WebSocket.OPEN) {
      result.push(c);
    }
  }
  return result;
}

wss.on('connection', (ws, req) => {
  const params = url.parse(req.url, true).query;
  const role = params.role || 'app';
  const token = params.token || '';

  if (TOKEN && token !== TOKEN) {
    ws.close(4001, 'invalid token');
    return;
  }

  const id = genId();
  const meta = {
    id,
    role,
    connectedAt: new Date().toISOString(),
    remote: req.socket.remoteAddress,
  };
  connections.set(id, { ws, role, metadata: meta });
  console.log(`[+] ${role}:${id} from ${meta.remote}`);

  ws.send(JSON.stringify({ type: 'connected', id, role }));

  ws.on('message', (data, isBinary) => {
    const targetRole = role === 'app' ? 'agent' : 'app';
    const targets = getClients(targetRole);

    if (isBinary) {
      // binary = audio chunk, forward to all opposite-role clients
      for (const t of targets) {
        t.ws.send(data, { binary: true });
      }
      return;
    }

    // text message: forward to all opposite-role clients
    const msgStr = data.toString();
    for (const t of targets) {
      t.ws.send(msgStr);
    }
  });

  ws.on('close', () => {
    connections.delete(id);
    console.log(`[-] ${role}:${id}`);
  });

  ws.on('error', (err) => {
    console.error(`[!] ${id}:`, err.message);
    connections.delete(id);
  });
});

server.listen(PORT, () => {
  console.log(`Wangcai Relay on port ${PORT}`);
  if (TOKEN) console.log('Auth enabled');
});
