const express = require("express");
const { conectar, getSock } = require("./connection");
const { setupMessageHandlers } = require("./handlers/messages");

const app = express();
app.use(express.json());

let composingTimersRef = null;

// Tenta conectar ao iniciar
conectar((sock) => {
  // Quando conectado, injeta os handlers
  const handlers = setupMessageHandlers(sock);
  composingTimersRef = handlers.composingTimers;
});

// ─── API endpoints (consumidos pelo backend python) ───

app.post("/send", async (req, res) => {
  const { phone, text } = req.body;
  const sock = getSock();
  if (!sock) return res.status(503).json({ error: "Nao conectado" });
  
  try {
    // phone (fornecido pelo backend como reply_jid) pode ser @lid ou numérico
    const jid = phone.includes("@") ? phone : phone + "@s.whatsapp.net";
    
    if (composingTimersRef && composingTimersRef[jid]) {
      clearInterval(composingTimersRef[jid]);
      delete composingTimersRef[jid];
    }
    
    try { await sock.sendPresenceUpdate("paused", jid); } catch (_) {}
    
    await sock.sendMessage(jid, { text: text });
    res.json({ ok: true });
  } catch (e) {
    console.error("Erro ao enviar mensagem:", e.message);
    res.status(500).json({ error: e.message });
  }
});

app.post("/send-document", async (req, res) => {
  const { phone, url, filename, caption } = req.body;
  const sock = getSock();
  if (!sock) return res.status(503).json({ error: "Nao conectado" });
  if (!url) return res.status(400).json({ error: "url é obrigatório" });
  
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Falha ao baixar documento: ${response.status}`);
    const buffer = Buffer.from(await response.arrayBuffer());
    
    const jid = phone.includes("@") ? phone : phone + "@s.whatsapp.net";
    
    if (composingTimersRef && composingTimersRef[jid]) {
      clearInterval(composingTimersRef[jid]);
      delete composingTimersRef[jid];
    }
    
    try { await sock.sendPresenceUpdate("paused", jid); } catch (_) {}
    
    await sock.sendMessage(jid, {
      document: buffer,
      mimetype: "application/pdf",
      fileName: filename || "tabela_servicos.pdf",
      caption: caption || ""
    });
    
    res.json({ ok: true });
  } catch (e) {
    console.error("Erro ao enviar documento:", e.message);
    res.status(500).json({ error: e.message });
  }
});

app.listen(3000, function() { 
  console.log("Baileys API rodando na porta 3000"); 
});