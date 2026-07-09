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
let reconnectTimer = null;
let qrWatchdogTimer = null;
let connectionGeneration = 0;
const statusListeners = new Set();
const AUTH_DIR = "./auth";
const QR_WATCHDOG_MS = 70000;

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

function clearConnectionTimers() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (qrWatchdogTimer) clearTimeout(qrWatchdogTimer);
  reconnectTimer = null;
  qrWatchdogTimer = null;
}

function detachSocketListeners(socket) {
  if (!socket?.ev) return;
  socket.ev.removeAllListeners("connection.update");
  socket.ev.removeAllListeners("creds.update");
  socket.ev.removeAllListeners("messages.upsert");
}

async function closeCurrentSocket({ remoteLogout = false } = {}) {
  clearConnectionTimers();
  connectionGeneration += 1;
  isConnecting = false;

  const current = sock;
  sock = null;
  if (!current) return;

  detachSocketListeners(current);
  try {
    if (remoteLogout) await current.logout();
    else current.end?.();
  } catch (_) {
    try {
      current.end?.();
    } catch (_) {}
  }
}

function scheduleReconnect(delayMs, generation) {
  clearConnectionTimers();
  reconnectTimer = setTimeout(() => {
    if (generation !== connectionGeneration) return;
    conectar(activeConnectionCallback).catch((error) => {
      console.error("Erro ao reconectar WhatsApp:", error.message);
    });
  }, delayMs);
}

function startQrWatchdog(generation) {
  if (qrWatchdogTimer) clearTimeout(qrWatchdogTimer);
  qrWatchdogTimer = setTimeout(async () => {
    if (generation !== connectionGeneration || sessionState.status !== "waiting_qr") return;
    console.log("QR Code expirou. Gerando um novo automaticamente.");
    await closeCurrentSocket();
    conectar(activeConnectionCallback).catch((error) => {
      console.error("Erro ao renovar QR Code:", error.message);
    });
  }, QR_WATCHDOG_MS);
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
  await closeCurrentSocket({ remoteLogout: true });
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
  clearConnectionTimers();
  const generation = ++connectionGeneration;
  updateState({
    status: "reconnecting",
    lastReconnectAt: nowISO(),
    lastError: null,
  });

  let state;
  let saveCreds;
  let newSocket;
  try {
    ({ state, saveCreds } = await useMultiFileAuthState(AUTH_DIR));
    newSocket = makeWASocket({
      auth: state,
      printQRInTerminal: false,
      keepAliveIntervalMs: 10000,
      browser: ["Ubuntu", "Chrome", "20.0.04"],
      logger: pino({ level: "error" }),
    });
  } catch (error) {
    isConnecting = false;
    updateState({
      status: "disconnected",
      lastError: error.message,
      disconnectReason: "connection_start_failed",
    });
    throw error;
  }
  sock = newSocket;

  if (typeof store.bind === "function") store.bind(newSocket.ev);

  newSocket.ev.on("connection.update", async ({ qr, connection, lastDisconnect }) => {
    if (generation !== connectionGeneration || sock !== newSocket) return;
    if (qr) {
      console.log("QR Code gerado para conexao pelo painel.");
      updateState({
        status: "waiting_qr",
        qr,
        qrUpdatedAt: nowISO(),
        disconnectReason: null,
      });
      startQrWatchdog(generation);
    }

    if (connection === "open") {
      clearConnectionTimers();
      const userPhone = newSocket.user?.id ? newSocket.user.id.split(":")[0].split("@")[0] : null;
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
        activeConnectionCallback(newSocket);
      }
    }

    if (connection === "close") {
      isConnecting = false;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const reason = statusCode ? String(statusCode) : lastDisconnect?.error?.message || "connection_closed";
      if (sock === newSocket) sock = null;

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
        scheduleReconnect(2000, generation);
      } else {
        console.log("Conexao caiu, tentando reconectar...");
        updateState({
          status: "reconnecting",
          qr: null,
          connectedAt: null,
          disconnectReason: reason,
          lastError: reason,
        });
        scheduleReconnect(5000, generation);
      }
    }
  });

  newSocket.ev.on("creds.update", saveCreds);

  return newSocket;
}

async function reconnect() {
  updateState({ status: "reconnecting", lastReconnectAt: nowISO() });
  await closeCurrentSocket();
  return conectar(activeConnectionCallback);
}

async function disconnect() {
  // No painel, desconectar significa trocar de numero: encerra a conta atual,
  // limpa a sessao e inicia imediatamente um novo pareamento.
  await closeCurrentSocket({ remoteLogout: true });
  clearAuthDirectory();
  updateState({
    status: "reconnecting",
    qr: null,
    connectedAt: null,
    connectedNumber: null,
    qrUpdatedAt: null,
    lastError: null,
    disconnectReason: "switching_account",
  });
  return conectar(activeConnectionCallback);
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
