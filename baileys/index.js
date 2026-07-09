const express = require("express");
const QRCode = require("qrcode");
const {
  conectar,
  reconnect,
  disconnect,
  logout,
  getSock,
  getStatus,
  subscribeStatus,
  markActivity,
} = require("./connection");
const { setupMessageHandlers } = require("./handlers/messages");

const app = express();
app.use(express.json({ limit: "20mb" }));

let composingTimersRef = null;
let handlersSocketRef = null;

function attachHandlers(sock) {
  if (!sock || handlersSocketRef === sock) return;
  const handlers = setupMessageHandlers(sock);
  composingTimersRef = handlers.composingTimers;
  handlersSocketRef = sock;
}

conectar(attachHandlers);

async function getQrPayload() {
  const status = getStatus();
  if (!status.qr) return { qr: null, qrImage: null, qrUpdatedAt: status.qrUpdatedAt };
  const qrImage = await QRCode.toDataURL(status.qr, {
    errorCorrectionLevel: "M",
    margin: 2,
    scale: 6,
  });
  return { qr: status.qr, qrImage, qrUpdatedAt: status.qrUpdatedAt };
}

function ensureConnected(res) {
  const sock = getSock();
  if (!sock || getStatus().status !== "connected") {
    res.status(503).json({ error: "WhatsApp nao conectado", status: getStatus() });
    return null;
  }
  return sock;
}

app.get("/status", (req, res) => {
  res.json(getStatus());
});

app.get("/info", (req, res) => {
  res.json(getStatus());
});

app.get("/health", (req, res) => {
  const status = getStatus();
  res.status(status.status === "connected" ? 200 : 503).json({
    ok: status.status === "connected",
    status,
  });
});

app.get("/qrcode", async (req, res) => {
  try {
    res.json(await getQrPayload());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post("/connect", async (req, res) => {
  try {
    const sock = await conectar(attachHandlers);
    attachHandlers(sock);
    res.json(getStatus());
  } catch (error) {
    res.status(500).json({ error: error.message, status: getStatus() });
  }
});

app.post("/reconnect", async (req, res) => {
  try {
    const sock = await reconnect();
    attachHandlers(sock);
    res.json(getStatus());
  } catch (error) {
    res.status(500).json({ error: error.message, status: getStatus() });
  }
});

app.post("/disconnect", async (req, res) => {
  try {
    await disconnect();
    res.json(getStatus());
  } catch (error) {
    res.status(500).json({ error: error.message, status: getStatus() });
  }
});

app.post("/logout", async (req, res) => {
  try {
    const sock = await logout();
    attachHandlers(sock);
    res.json(getStatus());
  } catch (error) {
    res.status(500).json({ error: error.message, status: getStatus() });
  }
});

app.get("/events", (req, res) => {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });

  const send = (payload) => {
    res.write(`data: ${JSON.stringify(payload)}\n\n`);
  };
  const unsubscribe = subscribeStatus(send);
  const heartbeat = setInterval(() => send({ ...getStatus(), heartbeat: true }), 25000);

  req.on("close", () => {
    clearInterval(heartbeat);
    unsubscribe();
  });
});

app.post("/send", async (req, res) => {
  const { phone, text } = req.body;
  const sock = ensureConnected(res);
  if (!sock) return;

  try {
    const jid = phone.includes("@") ? phone : phone + "@s.whatsapp.net";

    if (composingTimersRef && composingTimersRef[jid]) {
      clearInterval(composingTimersRef[jid]);
      delete composingTimersRef[jid];
    }

    try {
      await sock.sendPresenceUpdate("paused", jid);
    } catch (_) {}

    await sock.sendMessage(jid, { text });
    markActivity();
    res.json({ ok: true });
  } catch (e) {
    console.error("Erro ao enviar mensagem:", e.message);
    res.status(500).json({ error: e.message });
  }
});

app.post("/send-document", async (req, res) => {
  const { phone, url, filename, caption } = req.body;
  const sock = ensureConnected(res);
  if (!sock) return;
  if (!url) return res.status(400).json({ error: "url e obrigatorio" });

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Falha ao baixar documento: ${response.status}`);
    const buffer = Buffer.from(await response.arrayBuffer());

    const jid = phone.includes("@") ? phone : phone + "@s.whatsapp.net";

    if (composingTimersRef && composingTimersRef[jid]) {
      clearInterval(composingTimersRef[jid]);
      delete composingTimersRef[jid];
    }

    try {
      await sock.sendPresenceUpdate("paused", jid);
    } catch (_) {}

    await sock.sendMessage(jid, {
      document: buffer,
      mimetype: "application/pdf",
      fileName: filename || "tabela_servicos.pdf",
      caption: caption || "",
    });

    markActivity();
    res.json({ ok: true });
  } catch (e) {
    console.error("Erro ao enviar documento:", e.message);
    res.status(500).json({ error: e.message });
  }
});

app.listen(3000, function () {
  console.log("Baileys API rodando na porta 3000");
});
