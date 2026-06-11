const { getSenderNumber } = require('../utils/jid');

// ─── Estado Global para as Mensagens ───────────────
const msgBuffer = {}; // { phone: { timer, texts[], pushName, rawJid, resolvedJid } }
const composingTimers = {}; // { jid: timerId }
const DEBOUNCE_MS = 0;

function setupMessageHandlers(sock) {
  async function flushBuffer(phone) {
    const buf = msgBuffer[phone];
    if (!buf) return;
    delete msgBuffer[phone];

    const combinedText = buf.texts.join("\n").trim();
    if (!combinedText) return;

    console.log(`[debounce] Processando ${buf.texts.length} msg(s) de ${phone}: "${combinedText.slice(0, 60)}"`);

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
      let profile_pic = null;
      // Get profile pic using resolved JID first, then raw JID
      try {
        const queryJid = phone.includes("@") ? phone : phone + "@s.whatsapp.net";
        profile_pic = await sock.profilePictureUrl(queryJid, "image");
      } catch (_) {
        try { profile_pic = await sock.profilePictureUrl(buf.rawJid, "image"); } catch (_) {}
      }

      const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
      await fetch(`${backendUrl}/webhook/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phone, // Normalized phone (e.g. 558699999999)
          phone_for_reply: buf.rawJid, // Original JID (e.g. 123123@lid)
          message: combinedText,
          profile_pic: profile_pic,
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
    
    // Mark as read
    try {
      await sock.readMessages([msg.key]);
    } catch (err) {
      console.error("Erro ao marcar como lida:", err);
    }
    
    // Use centralized JID resolution
    const { rawJid, resolvedPhone } = getSenderNumber(msg, sock);
    const phone = resolvedPhone;
    const pushName = msg.pushName || "";
    const text = (msg.message.conversation) || (msg.message.extendedTextMessage && msg.message.extendedTextMessage.text) || "";
    
    if (!text) return;

    // ── Debounce ──
    if (msgBuffer[phone]) {
      clearTimeout(msgBuffer[phone].timer);
      msgBuffer[phone].texts.push(text);
    } else {
      msgBuffer[phone] = { texts: [text], pushName, rawJid };
    }
    msgBuffer[phone].timer = setTimeout(() => flushBuffer(phone), DEBOUNCE_MS);
    console.log(`[debounce] Mensagem de ${phone} adicionada ao buffer (${msgBuffer[phone].texts.length} pendente(s))`);
  });

  return { composingTimers };
}

module.exports = { setupMessageHandlers };
