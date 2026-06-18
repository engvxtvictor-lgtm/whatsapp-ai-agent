const { getSenderNumber } = require('../utils/jid');
const { downloadMediaMessage } = require('@whiskeysockets/baileys');
const { markActivity } = require('../connection');

// ─── Estado Global para as Mensagens ───────────────
const msgBuffer = {}; // { phone: { timer, texts[], pushName, rawJid, resolvedJid } }
const composingTimers = {}; // { jid: timerId }
const DEBOUNCE_MS = 3000;

function shouldIgnoreJid(remoteJid) {
  if (!remoteJid) return true;
  if (remoteJid.endsWith("@g.us")) return "grupo";
  if (remoteJid.endsWith("@newsletter")) return "canal/newsletter";
  if (remoteJid === "status@broadcast" || remoteJid.endsWith("@broadcast")) return "broadcast/status";
  return "";
}

function setupMessageHandlers(sock) {
  async function flushBuffer(phone) {
    const buf = msgBuffer[phone];
    if (!buf) return;
    delete msgBuffer[phone];

    const combinedText = buf.texts.join("\n").trim();
    if (!combinedText && !buf.media) return;

    console.log(`[debounce] Processando de ${phone}: texto=${combinedText.length} media=${buf.media ? buf.media.type : 'none'}`);

    // Show "typing..."
    try { await sock.sendPresenceUpdate("composing", buf.rawJid); } catch (_) {}
    if (composingTimers[buf.rawJid]) clearInterval(composingTimers[buf.rawJid]);
    composingTimers[buf.rawJid] = setInterval(async () => {
      try { await sock.sendPresenceUpdate("composing", buf.rawJid); } catch (_) {}
    }, 10000);
    
    // Auto clear typing after 90s
    setTimeout(() => {
      if (composingTimers[buf.rawJid]) {
        clearInterval(composingTimers[buf.rawJid]);
        delete composingTimers[buf.rawJid];
        try { sock.sendPresenceUpdate("paused", buf.rawJid); } catch (_) {}
      }
    }, 90000);

    try {
      const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
      await fetch(`${backendUrl}/webhook/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phone, // Normalized phone (e.g. 558699999999)
          phone_for_reply: buf.rawJid, // Original JID (e.g. 123123@lid)
          message: combinedText,
          media: buf.media,
          push_name: buf.pushName
        })
      });
    } catch (e) {
      console.error("Erro webhook (debounce):", e.message);
      // Stop typing on error
      if (composingTimers[buf.rawJid]) {
        clearInterval(composingTimers[buf.rawJid]);
        delete composingTimers[buf.rawJid];
      }
      try { await sock.sendPresenceUpdate("paused", buf.rawJid); } catch (_) {}
    }
  }

  sock.ev.on("messages.upsert", async ({ messages }) => {
    const msg = messages[0];
    if (!msg.message || msg.key.fromMe) return;
    markActivity();

    const remoteJid = msg.key.remoteJid || "";
    const ignoredReason = shouldIgnoreJid(remoteJid);
    if (ignoredReason) {
      console.log(`[${ignoredReason}] Ignorando mensagem fora do atendimento 1:1: ${remoteJid}`);
      return;
    }
    
    // Mark as read
    try {
      await sock.readMessages([msg.key]);
    } catch (err) {
      console.error("Erro ao marcar como lida:", err);
    }
    
    // Use centralized JID resolution
    const { rawJid, resolvedPhone } = await getSenderNumber(msg, sock);
    const phone = resolvedPhone;
    const pushName = msg.pushName || "";
    const text = (msg.message.conversation) || (msg.message.extendedTextMessage && msg.message.extendedTextMessage.text) || (msg.message.imageMessage && msg.message.imageMessage.caption) || "";
    
    // Check for media
    let media = null;
    let messageType = Object.keys(msg.message || {})[0];

    if (messageType === 'imageMessage' || messageType === 'audioMessage' || messageType === 'ptvMessage') {
      try {
        const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger: console, reuploadRequest: sock.updateMediaMessage });
        const mimeType = msg.message[messageType].mimetype;
        const type = messageType === 'imageMessage' ? 'image' : 'audio';
        
        media = {
          type: type,
          mimetype: mimeType,
          data: buffer.toString('base64')
        };
      } catch (e) {
        console.error("Erro ao baixar media:", e);
      }
    }

    if (!text && !media) return;

    // ── Debounce ──
    if (msgBuffer[phone]) {
      clearTimeout(msgBuffer[phone].timer);
      if (text) msgBuffer[phone].texts.push(text);
      if (media) msgBuffer[phone].media = media; // Armazena apenas a última mídia no debounce
    } else {
      msgBuffer[phone] = { texts: text ? [text] : [], media: media, pushName, rawJid };
    }
    msgBuffer[phone].timer = setTimeout(() => flushBuffer(phone), DEBOUNCE_MS);
    console.log(`[debounce] Mensagem/Midia de ${phone} adicionada ao buffer (${msgBuffer[phone].texts.length} texto(s) pendente(s))`);
  });

  return { composingTimers };
}

module.exports = { setupMessageHandlers };
