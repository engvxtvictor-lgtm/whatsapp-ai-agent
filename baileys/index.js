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

async function conectar() {
  if (isConnecting) return
  isConnecting = true
  const { state, saveCreds } = await useMultiFileAuthState("./auth")
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    keepAliveIntervalMs: 10000,
    logger: require("pino")({ level: "silent" }),
  })
  sock.ev.on("connection.update", async ({ qr, connection, lastDisconnect }) => {
    if (qr) {
      console.log("Escaneie o QR Code:")
      qrcode.generate(qr, { small: true })
    }
    if (connection === "open") {
      console.log("WhatsApp conectado!")
      isConnecting = false
    }
    if (connection === "close") {
      isConnecting = false
      const code = new Boom(lastDisconnect && lastDisconnect.error).output.statusCode
      if (code === DisconnectReason.loggedOut) {
        fs.rmSync("./auth", { recursive: true, force: true })
        setTimeout(conectar, 2000)
      } else {
        setTimeout(conectar, 5000)
      }
    }
  })
  sock.ev.on("creds.update", saveCreds)
  sock.ev.on("messages.upsert", async ({ messages }) => {
    const msg = messages[0]
    if (!msg.message || msg.key.fromMe) return
    const phone = msg.key.remoteJid.replace("@s.whatsapp.net", "")
    const text = (msg.message.conversation) || (msg.message.extendedTextMessage && msg.message.extendedTextMessage.text) || ""
    if (!text) return
    console.log("Mensagem de " + phone + ": " + text)
    try {
      const backendUrl = process.env.BACKEND_URL || "http://localhost:8000"
      await fetch(`${backendUrl}/webhook/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: phone, message: text })
      })
    } catch (e) {
      console.error("Erro webhook:", e.message)
    }
  })
}

app.post("/send", async (req, res) => {
  const { phone, text } = req.body
  if (!sock) return res.status(503).json({ error: "Nao conectado" })
  try {
    await sock.sendMessage(phone + "@s.whatsapp.net", { text: text })
    res.json({ ok: true })
  } catch (e) {
    res.status(500).json({ error: e.message })
  }
})

app.listen(3000, function() { console.log("Baileys rodando na porta 3000") })
conectar()