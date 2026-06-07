const baileys = require("@whiskeysockets/baileys")
const makeWASocket = baileys.default
const { useMultiFileAuthState, DisconnectReason } = baileys
const { Boom } = require("@hapi/boom")
const express = require("express")
const qrcode = require("qrcode-terminal")
const fs = require("fs")

const app = express()
app.use(express.json())
let sock = null
let isConnecting = false

// Store em memória para resolver @lid → número real (compatível com todas as versões do Baileys)
let store = { contacts: {} }
try {
  const makeInMemoryStore = baileys.makeInMemoryStore
  if (typeof makeInMemoryStore === "function") {
    store = makeInMemoryStore({})
    console.log("✅ makeInMemoryStore carregado com sucesso.")
  } else {
    console.log("⚠️ makeInMemoryStore não disponível nesta versão do Baileys. Usando fallback.")
  }
} catch (e) {
  console.log("⚠️ Erro ao inicializar store:", e.message, "- Usando fallback.")
}

/**
 * Tenta resolver um JID @lid para o número real do WhatsApp.
 * Retorna o JID original se não conseguir resolver.
 */
async function resolveJid(jid) {
  if (!jid.includes("@lid")) return jid

  try {
    // Tenta via store de contatos (sincronizado pelo Baileys)
    const contacts = store.contacts || {}
    for (const [contactJid, contact] of Object.entries(contacts)) {
      if (contact.lid === jid || contact.id === jid) {
        if (contactJid.includes("@s.whatsapp.net")) {
          console.log(`✅ LID resolvido: ${jid} → ${contactJid}`)
          return contactJid
        }
      }
    }

    // Tenta via sock.onWhatsApp se tiver o LID numérico
    const lidNumber = jid.split("@")[0]
    if (/^\d+$/.test(lidNumber)) {
      const results = await sock.onWhatsApp(lidNumber + "@s.whatsapp.net").catch(() => [])
      if (results && results.length > 0 && results[0].exists) {
        console.log(`✅ LID resolvido via onWhatsApp: ${jid} → ${results[0].jid}`)
        return results[0].jid
      }
    }
  } catch (e) {
    console.error("Erro ao resolver LID:", e.message)
  }

  console.log(`⚠️  Não foi possível resolver LID: ${jid}`)
  return jid
}

async function conectar() {
  if (isConnecting) return
  isConnecting = true
  const { state, saveCreds } = await useMultiFileAuthState("./auth")
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    keepAliveIntervalMs: 10000,
    browser: ["Ubuntu", "Chrome", "20.0.04"],
    logger: require("pino")({ level: "error" }),
  })

  // Vincula o store ao socket para capturar contatos automaticamente (se disponível)
  if (typeof store.bind === "function") store.bind(sock.ev)

  sock.ev.on("connection.update", async ({ qr, connection, lastDisconnect }) => {
    if (qr) {
      console.log("Escaneie o QR Code:")
      qrcode.generate(qr, { small: true })
    }
    if (connection === "open") {
      const userPhone = sock.user?.id ? sock.user.id.split(":")[0].split("@")[0] : "Desconhecido";
      console.log("✅ WhatsApp conectado! O número do robô é: +" + userPhone);
      isConnecting = false
    }
    if (connection === "close") {
      isConnecting = false
      const statusCode = lastDisconnect?.error?.output?.statusCode
      if (statusCode === DisconnectReason.loggedOut) {
        fs.rmSync("./auth", { recursive: true, force: true })
        setTimeout(conectar, 2000)
      } else {
        setTimeout(conectar, 5000)
      }
    }
  })
  sock.ev.on("creds.update", saveCreds)

  // ─── Debounce: acumula mensagens por 3s antes de processar ───────────────
  // Evita respostas múltiplas quando o usuário manda várias msgs seguidas
  const msgBuffer = {} // { phone: { timer, texts[], pushName, rawJid, resolvedJid } }
  const DEBOUNCE_MS = 3000

  async function flushBuffer(phone) {
    const buf = msgBuffer[phone]
    if (!buf) return
    delete msgBuffer[phone]

    const combinedText = buf.texts.join("\n").trim()
    if (!combinedText) return

    console.log(`[debounce] Processando ${buf.texts.length} msg(s) de ${phone}: "${combinedText.slice(0,60)}"`)

    try {
      let profile_pic = null
      try {
        profile_pic = await sock.profilePictureUrl(buf.resolvedJid, "image")
      } catch (_) {
        try { profile_pic = await sock.profilePictureUrl(buf.rawJid, "image") } catch (_) {}
      }

      const backendUrl = process.env.BACKEND_URL || "http://localhost:8000"
      await fetch(`${backendUrl}/webhook/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phone,
          phone_for_reply: buf.rawJid,
          message: combinedText,
          profile_pic: profile_pic,
          push_name: buf.pushName
        })
      })
    } catch (e) {
      console.error("Erro webhook (debounce):", e.message)
    }
  }
  // ─────────────────────────────────────────────────────────────────────────

  sock.ev.on("messages.upsert", async ({ messages }) => {
    const msg = messages[0]
    if (!msg.message || msg.key.fromMe) return
    
    // Marca a mensagem como lida (tracinhos azuis)
    try {
      await sock.readMessages([msg.key]);
    } catch (err) {
      console.error("Erro ao marcar como lida:", err);
    }
    
    const rawJid = msg.key.remoteJid
    const resolvedJid = await resolveJid(rawJid)
    const phone = resolvedJid.replace("@s.whatsapp.net", "").replace("@lid", "")
    const pushName = msg.pushName || ""
    const text = (msg.message.conversation) || (msg.message.extendedTextMessage && msg.message.extendedTextMessage.text) || ""
    if (!text) return

    // ── Debounce: acumula mensagens e só processa após 3s de silêncio ──
    if (msgBuffer[phone]) {
      clearTimeout(msgBuffer[phone].timer)
      msgBuffer[phone].texts.push(text)
    } else {
      msgBuffer[phone] = { texts: [text], pushName, rawJid, resolvedJid }
    }
    msgBuffer[phone].timer = setTimeout(() => flushBuffer(phone), DEBOUNCE_MS)
    console.log(`[debounce] Mensagem de ${phone} adicionada ao buffer (${msgBuffer[phone].texts.length} pendente(s))`)
  })
}

app.post("/send", async (req, res) => {
  const { phone, text } = req.body
  if (!sock) return res.status(503).json({ error: "Nao conectado" })
  try {
    const jid = phone.includes("@") ? phone : phone + "@s.whatsapp.net"
    await sock.sendMessage(jid, { text: text })
    res.json({ ok: true })
  } catch (e) {
    res.status(500).json({ error: e.message })
  }
})

app.post("/send-document", async (req, res) => {
  const { phone, url, filename, caption } = req.body
  if (!sock) return res.status(503).json({ error: "Nao conectado" })
  if (!url) return res.status(400).json({ error: "url é obrigatório" })
  try {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Falha ao baixar documento: ${response.status}`)
    const buffer = Buffer.from(await response.arrayBuffer())
    const jid = phone.includes("@") ? phone : phone + "@s.whatsapp.net"
    await sock.sendMessage(jid, {
      document: buffer,
      mimetype: "application/pdf",
      fileName: filename || "tabela_servicos.pdf",
      caption: caption || ""
    })
    res.json({ ok: true })
  } catch (e) {
    res.status(500).json({ error: e.message })
  }
})

app.listen(3000, function() { console.log("Baileys rodando na porta 3000") })
conectar()