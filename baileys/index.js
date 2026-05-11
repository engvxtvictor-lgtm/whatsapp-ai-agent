const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys')
const express = require('express')
const qrcode = require('qrcode-terminal')

const app = express()
app.use(express.json())

let sock = null

async function conectar() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth')

  sock = makeWASocket({ auth: state, printQRInTerminal: false })

  sock.ev.on('connection.update', ({ qr, connection }) => {
    if (qr) {
      console.log('Escaneie o QR Code abaixo com seu WhatsApp:')
      qrcode.generate(qr, { small: true })
    }
    if (connection === 'open') console.log('✅ WhatsApp conectado!')
    if (connection === 'close') {
      console.log('Conexão perdida. Reconectando...')
      conectar()
    }
  })

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('messages.upsert', async ({ messages }) => {
    const msg = messages[0]
    if (!msg.message || msg.key.fromMe) return

    const phone = msg.key.remoteJid.replace('@s.whatsapp.net', '')
    const text = msg.message.conversation
              || msg.message.extendedTextMessage?.text
              || ''

    if (!text) return

    console.log(`📩 Mensagem de ${phone}: ${text}`)

    try {
      await fetch('http://localhost:8000/webhook/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, message: text })
      })
    } catch (e) {
      console.error('Erro ao chamar webhook Python:', e.message)
    }
  })
}

app.post('/send', async (req, res) => {
  const { phone, text } = req.body
  if (!sock) return res.status(503).json({ error: 'WhatsApp não conectado' })

  try {
    await sock.sendMessage(`${phone}@s.whatsapp.net`, { text })
    res.json({ ok: true })
  } catch (e) {
    res.status(500).json({ error: e.message })
  }
})

app.listen(3000, () => console.log('🚀 Baileys rodando na porta 3000'))
conectar()