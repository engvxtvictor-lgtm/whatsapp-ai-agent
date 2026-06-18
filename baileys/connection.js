const baileys = require("@whiskeysockets/baileys");
const makeWASocket = baileys.default;
const { useMultiFileAuthState, DisconnectReason } = baileys;
const fs = require("fs");
const path = require("path");
const pino = require("pino");
const packageInfo = require("./package.json");

let isConnecting = false;
let sock = null;
let store = { contacts: {} };
let activeConnectionCallback = null;
const statusListeners = new Set();
const AUTH_DIR = "./auth";

const sessionState = {
  clinicId: process.env.CLINIC_ID || "default",
  sessionId: process.env.WHATSAPP_SESSION_ID || "default",
  status: "disconnected",
  qr: null,
  qrUpdatedAt: null,
  connectedAt: null,
  lastActivityAt: null,
  lastReconnectAt: null,
  disconnectReason: null,
  whatsappVersion: packageInfo.dependencies?.["@whiskeysockets/baileys"] || "unknown",
  connectedNumber: null,
  lastError: null,
  updatedAt: new Date().toISOString(),
};

try {
  const makeInMemoryStore = baileys.makeInMemoryStore;
  if (typeof makeInMemoryStore === "function") {
    store = makeInMemoryStore({});
    console.log("makeInMemoryStore carregado com sucesso.");
  } else {
    console.log("makeInMemoryStore nao disponivel nesta versao do Baileys. Usando fallback.");
  }
} catch (e) {
  console.log("Erro ao inicializar store:", e.message, "- Usando fallback.");
}

function nowISO() {
  return new Date().toISOString();
}

function updateState(patch) {
  Object.assign(sessionState, patch, { updatedAt: nowISO() });
  const snapshot = getStatus();
  for (const listener of statusListeners) {
    try {
      listener(snapshot);
    } catch (_) {}
  }
}

function clearAuthDirectory() {
  if (!fs.existsSync(AUTH_DIR)) return;
  for (const entry of fs.readdirSync(AUTH_DIR)) {
    fs.rmSync(path.join(AUTH_DIR, entry), { recursive: true, force: true });
  }
}

function getUptimeSeconds() {
  if (!sessionState.connectedAt) return 0;
  return Math.max(0, Math.floor((Date.now() - new Date(sessionState.connectedAt).getTime()) / 1000));
}

function getStatus() {
  return {
    ...sessionState,
    isConnected: sessionState.status === "connected",
    uptimeSeconds: getUptimeSeconds(),
  };
}

function subscribeStatus(listener) {
  statusListeners.add(listener);
  listener(getStatus());
  return () => statusListeners.delete(listener);
}

function markActivity() {
  updateState({ lastActivityAt: nowISO() });
}

async function destroyCurrentSocket(reason = "manual") {
  if (!sock) return;
  const current = sock;
  sock = null;
  try {
    current.ev.removeAllListeners("connection.update");
    current.ev.removeAllListeners("creds.update");
    current.ev.removeAllListeners("messages.upsert");
  } catch (_) {}
  try {
    await current.logout();
  } catch (_) {
    try {
      current.end?.();
    } catch (_) {}
  }
  updateState({
    status: "disconnected",
    qr: null,
    disconnectReason: reason,
    connectedAt: null,
    connectedNumber: null,
  });
}

async function conectar(onConnectionEstablished) {
  if (onConnectionEstablished) activeConnectionCallback = onConnectionEstablished;
  if (isConnecting) return sock;
  if (sock && sessionState.status === "connected") return sock;

  isConnecting = true;
  updateState({
    status: "reconnecting",
    lastReconnectAt: nowISO(),
    lastError: null,
  });

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    keepAliveIntervalMs: 10000,
    browser: ["Ubuntu", "Chrome", "20.0.04"],
    logger: pino({ level: "error" }),
  });

  if (typeof store.bind === "function") store.bind(sock.ev);

  sock.ev.on("connection.update", async ({ qr, connection, lastDisconnect }) => {
    if (qr) {
      console.log("QR Code gerado para conexao pelo painel.");
      updateState({
        status: "waiting_qr",
        qr,
        qrUpdatedAt: nowISO(),
        disconnectReason: null,
      });
    }

    if (connection === "open") {
      const userPhone = sock.user?.id ? sock.user.id.split(":")[0].split("@")[0] : null;
      console.log("WhatsApp conectado! O numero do robo e: +" + (userPhone || "desconhecido"));
      isConnecting = false;
      updateState({
        status: "connected",
        qr: null,
        connectedAt: sessionState.connectedAt || nowISO(),
        lastActivityAt: nowISO(),
        disconnectReason: null,
        connectedNumber: userPhone,
      });

      if (activeConnectionCallback) {
        activeConnectionCallback(sock);
      }
    }

    if (connection === "close") {
      isConnecting = false;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const reason = statusCode ? String(statusCode) : lastDisconnect?.error?.message || "connection_closed";
      sock = null;

      if (statusCode === DisconnectReason.loggedOut) {
        console.log("WhatsApp deslogado. Limpando credenciais e aguardando novo QR.");
        try {
          clearAuthDirectory();
        } catch (error) {
          console.error("Erro ao limpar credenciais do WhatsApp:", error.message);
        }
        updateState({
          status: "waiting_qr",
          qr: null,
          connectedAt: null,
          connectedNumber: null,
          disconnectReason: reason,
          lastError: reason,
        });
        setTimeout(() => conectar(activeConnectionCallback), 2000);
      } else {
        console.log("Conexao caiu, tentando reconectar...");
        updateState({
          status: "reconnecting",
          qr: null,
          connectedAt: null,
          disconnectReason: reason,
          lastError: reason,
        });
        setTimeout(() => conectar(activeConnectionCallback), 5000);
      }
    }
  });

  sock.ev.on("creds.update", saveCreds);

  return sock;
}

async function reconnect() {
  updateState({ status: "reconnecting", lastReconnectAt: nowISO() });
  if (sock) {
    try {
      sock.end?.();
    } catch (_) {}
    sock = null;
  }
  return conectar(activeConnectionCallback);
}

async function disconnect() {
  if (sock) {
    try {
      sock.end?.();
    } catch (_) {}
    sock = null;
  }
  updateState({
    status: "disconnected",
    qr: null,
    connectedAt: null,
    disconnectReason: "manual_disconnect",
  });
}

async function logout() {
  await destroyCurrentSocket("manual_logout");
  clearAuthDirectory();
  updateState({
    status: "waiting_qr",
    qr: null,
    connectedAt: null,
    connectedNumber: null,
    disconnectReason: "manual_logout",
  });
  return conectar(activeConnectionCallback);
}

function getSock() {
  return sock;
}

module.exports = {
  conectar,
  reconnect,
  disconnect,
  logout,
  getSock,
  getStatus,
  subscribeStatus,
  markActivity,
  store,
};
