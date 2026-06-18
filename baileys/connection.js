const baileys = require("@whiskeysockets/baileys");
const makeWASocket = baileys.default;
const { useMultiFileAuthState, DisconnectReason } = baileys;
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");
const pino = require("pino");

let isConnecting = false;
let sock = null;
let store = { contacts: {} };
const AUTH_DIR = "./auth";

function clearAuthDirectory() {
  if (!fs.existsSync(AUTH_DIR)) return;
  for (const entry of fs.readdirSync(AUTH_DIR)) {
    fs.rmSync(path.join(AUTH_DIR, entry), { recursive: true, force: true });
  }
}

try {
  const makeInMemoryStore = baileys.makeInMemoryStore;
  if (typeof makeInMemoryStore === "function") {
    store = makeInMemoryStore({});
    console.log("✅ makeInMemoryStore carregado com sucesso.");
  } else {
    console.log("⚠️ makeInMemoryStore não disponível nesta versão do Baileys. Usando fallback.");
  }
} catch (e) {
  console.log("⚠️ Erro ao inicializar store:", e.message, "- Usando fallback.");
}

async function conectar(onConnectionEstablished) {
  if (isConnecting) return;
  isConnecting = true;

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    keepAliveIntervalMs: 10000,
    browser: ["Ubuntu", "Chrome", "20.0.04"],
    logger: pino({ level: "error" }),
  });

  // Vincula o store ao socket para capturar contatos automaticamente
  if (typeof store.bind === "function") store.bind(sock.ev);

  sock.ev.on("connection.update", async ({ qr, connection, lastDisconnect }) => {
    if (qr) {
      console.log("Escaneie o QR Code:");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "open") {
      const userPhone = sock.user?.id ? sock.user.id.split(":")[0].split("@")[0] : "Desconhecido";
      console.log("✅ WhatsApp conectado! O número do robô é: +" + userPhone);
      isConnecting = false;
      
      if (onConnectionEstablished) {
        onConnectionEstablished(sock);
      }
    }
    if (connection === "close") {
      isConnecting = false;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      if (statusCode === DisconnectReason.loggedOut) {
        console.log("⚠️ Deslogado! Apagando credenciais e reiniciando...");
        try {
          clearAuthDirectory();
        } catch (error) {
          console.error("Erro ao limpar credenciais do WhatsApp:", error.message);
        }
        setTimeout(() => conectar(onConnectionEstablished), 2000);
      } else {
        console.log("⚠️ Conexão caiu, tentando reconectar...");
        setTimeout(() => conectar(onConnectionEstablished), 5000);
      }
    }
  });

  sock.ev.on("creds.update", saveCreds);
  
  return sock;
}

function getSock() {
  return sock;
}

module.exports = { conectar, getSock, store };
