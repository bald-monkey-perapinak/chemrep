import express from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import jwt from 'jsonwebtoken';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || '';
const JWT_STUB_MODE = process.env.BOARD_STUB_MODE === 'true';

const app = express();
const server = createServer(app);

app.use(express.static(join(__dirname, 'public')));
app.use('/assets', express.static(join(__dirname, 'assets')));

const wss = new WebSocketServer({ server });

const rooms = new Map();

function verifyToken(token) {
  if (!JWT_SECRET || JWT_STUB_MODE) return true;
  try {
    jwt.verify(token, JWT_SECRET);
    return true;
  } catch {
    return false;
  }
}

wss.on('connection', (ws, req) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathMatch = url.pathname.match(/^\/rooms\/(.+)$/);

  if (!pathMatch) {
    ws.close(4000, 'Invalid path. Use /rooms/{session_id}');
    return;
  }

  const token = url.searchParams.get('token');
  if (!verifyToken(token)) {
    ws.close(4001, 'Unauthorized');
    return;
  }

  const sessionId = pathMatch[1];

  if (!rooms.has(sessionId)) {
    rooms.set(sessionId, new Set());
  }
  rooms.get(sessionId).add(ws);

  console.log(`[board] Client connected to room ${sessionId} (total: ${rooms.get(sessionId).size})`);

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      broadcast(sessionId, msg, ws);
    } catch (e) {
      console.error('[board] Invalid message:', e.message);
    }
  });

  ws.on('close', () => {
    const room = rooms.get(sessionId);
    if (room) {
      room.delete(ws);
      if (room.size === 0) {
        rooms.delete(sessionId);
        console.log(`[board] Room ${sessionId} empty, removed`);
      } else {
        console.log(`[board] Client disconnected from ${sessionId} (remaining: ${room.size})`);
      }
    }
  });

  ws.on('error', (err) => {
    console.error(`[board] WebSocket error in room ${sessionId}:`, err.message);
  });
});

function broadcast(sessionId, message, exclude = null) {
  const room = rooms.get(sessionId);
  if (!room) return;
  const data = JSON.stringify(message);
  for (const client of room) {
    if (client !== exclude && client.readyState === WebSocket.OPEN) {
      client.send(data);
    }
  }
}

app.get('/health', (req, res) => {
  res.json({ status: 'ok', rooms: rooms.size });
});

server.listen(PORT, () => {
  console.log(`[board] Whiteboard server running on port ${PORT}`);
});
