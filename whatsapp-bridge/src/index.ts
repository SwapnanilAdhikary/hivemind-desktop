import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  type WASocket,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import pino from "pino";
import qrcode from "qrcode-terminal";
import { WebSocketServer, WebSocket } from "ws";
import path from "path";
import fs from "fs";

const AUTH_DIR = path.resolve(process.cwd(), "auth_info");
const WS_PORT = 8001;
const logger = pino({ level: "warn" });

console.log(`[WhatsApp Bridge] Auth directory: ${AUTH_DIR}`);

if (!fs.existsSync(AUTH_DIR)) {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  console.log("[WhatsApp Bridge] Created fresh auth directory");
}

let sock: WASocket | null = null;
const clients = new Set<WebSocket>();

const wss = new WebSocketServer({ port: WS_PORT });
console.log(`[WhatsApp Bridge] WebSocket server on ws://127.0.0.1:${WS_PORT}`);

wss.on("connection", (ws) => {
  clients.add(ws);
  console.log(`[WhatsApp Bridge] Python client connected (total: ${clients.size})`);

  ws.on("message", async (raw) => {
    try {
      const msg = JSON.parse(raw.toString());
      await handleCommand(msg, ws);
    } catch (e) {
      ws.send(JSON.stringify({ type: "error", error: String(e) }));
    }
  });

  ws.on("close", () => {
    clients.delete(ws);
    console.log(`[WhatsApp Bridge] Client disconnected (total: ${clients.size})`);
  });

  ws.send(
    JSON.stringify({
      type: "status",
      connected: sock !== null,
    })
  );
});

function broadcast(payload: object) {
  const data = JSON.stringify(payload);
  for (const client of clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(data);
    }
  }
}

async function handleCommand(msg: any, ws: WebSocket) {
  switch (msg.type) {
    case "send_message": {
      if (!sock) {
        ws.send(JSON.stringify({ type: "error", error: "Not connected" }));
        return;
      }
      const { jid, text } = msg;
      await sock.sendMessage(jid, { text });
      ws.send(JSON.stringify({ type: "message_sent", jid, text }));
      break;
    }

    case "get_status": {
      ws.send(
        JSON.stringify({
          type: "status",
          connected: sock !== null,
        })
      );
      break;
    }

    default:
      ws.send(JSON.stringify({ type: "error", error: `Unknown command: ${msg.type}` }));
  }
}

async function connectToWhatsApp() {
  console.log("[WhatsApp Bridge] Connecting to WhatsApp...");
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  const waVersion: [number, number, number] = [2, 3000, 1027934701];

  sock = makeWASocket({
    auth: state,
    logger,
    version: waVersion,
    browser: ["Agent Platform", "Chrome", "1.0.0"],
  });

  sock.ev.on("connection.update", (update) => {
    console.log("[WhatsApp Bridge] Connection update:", JSON.stringify(update, null, 2));

    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n[WhatsApp Bridge] ========== SCAN THIS QR CODE ==========\n");
      qrcode.generate(qr, { small: true });
      console.log("\n[WhatsApp Bridge] ==========================================\n");
      broadcast({ type: "qr", qr });
    }

    if (connection === "close") {
      const error = lastDisconnect?.error as Boom | undefined;
      const reason = error?.output?.statusCode;
      const shouldReconnect = reason !== DisconnectReason.loggedOut;
      console.log(`[WhatsApp Bridge] Disconnected. Reason: ${reason} (${error?.message || "unknown"}). Reconnecting: ${shouldReconnect}`);
      broadcast({ type: "disconnected", reason });

      if (shouldReconnect) {
        const delay = reason === 405 ? 10000 : 5000;
        console.log(`[WhatsApp Bridge] Retrying in ${delay / 1000}s...`);
        sock = null;
        setTimeout(connectToWhatsApp, delay);
      } else {
        sock = null;
      }
    }

    if (connection === "open") {
      console.log("[WhatsApp Bridge] Connected to WhatsApp!");
      broadcast({ type: "connected" });
    }
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("messages.upsert", ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (msg.key.fromMe) continue;

      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "";

      if (!text) continue;

      const sender = msg.key.remoteJid || "";
      const senderName = msg.pushName || sender.split("@")[0];

      console.log(`[WhatsApp Bridge] Message from ${senderName}: ${text.substring(0, 50)}`);

      broadcast({
        type: "new_message",
        data: {
          sender,
          sender_name: senderName,
          content: text,
          timestamp: new Date().toISOString(),
          message_id: msg.key.id,
          is_group: sender.endsWith("@g.us"),
        },
      });
    }
  });
}

connectToWhatsApp().catch((err) => {
  console.error("[WhatsApp Bridge] Failed to connect:", err);
});
