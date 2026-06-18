let whatsappEventSource = null;
let whatsappLastStatus = null;
let whatsappRendering = false;
let whatsappControlsBound = false;

function whatsappAuthHeaders() {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function whatsappStatusMeta(status) {
    const map = {
        connected: ["Conectado", "online", "O agente esta pronto para responder pacientes."],
        waiting_qr: ["Aguardando QR Code", "waiting", "Escaneie o QR Code pelo WhatsApp correto."],
        disconnected: ["Desconectado", "offline", "Clique em conectar ou reconectar para iniciar uma nova sessao."],
        reconnecting: ["Reconectando", "syncing", "Tentando restaurar a sessao automaticamente."],
    };
    return map[status] || ["Desconhecido", "offline", "Status nao identificado."];
}

function whatsappFormatDate(value) {
    if (!value) return "-";
    try {
        return new Date(value).toLocaleString("pt-BR");
    } catch (_) {
        return "-";
    }
}

function whatsappFormatUptime(seconds) {
    const total = Number(seconds || 0);
    if (!total) return "-";
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (hours) return `${hours}h ${minutes}min`;
    return `${minutes}min`;
}

function updateWhatsappStatus(status) {
    whatsappLastStatus = status || whatsappLastStatus || {};
    const [label, cssClass, description] = whatsappStatusMeta(whatsappLastStatus.status);
    const dot = document.getElementById("wa-status-dot");
    const labelEl = document.getElementById("wa-status-label");
    const descEl = document.getElementById("wa-status-description");
    const numberEl = document.getElementById("wa-connected-number");
    const updatedEl = document.getElementById("wa-updated-at");
    const activityEl = document.getElementById("wa-last-activity");
    const uptimeEl = document.getElementById("wa-uptime");

    if (dot) dot.className = `wa-status-dot ${cssClass}`;
    if (labelEl) labelEl.textContent = label;
    if (descEl) descEl.textContent = whatsappLastStatus.disconnectReason ? `${description} Motivo: ${whatsappLastStatus.disconnectReason}` : description;
    if (numberEl) numberEl.textContent = whatsappLastStatus.connectedNumber ? `+${whatsappLastStatus.connectedNumber}` : "-";
    if (updatedEl) updatedEl.textContent = whatsappFormatDate(whatsappLastStatus.updatedAt);
    if (activityEl) activityEl.textContent = whatsappFormatDate(whatsappLastStatus.lastActivityAt);
    if (uptimeEl) uptimeEl.textContent = whatsappFormatUptime(whatsappLastStatus.uptimeSeconds);

    if (whatsappLastStatus.status === "waiting_qr") {
        loadWhatsappQr();
    } else {
        const qrBox = document.getElementById("wa-qr-box");
        if (qrBox) qrBox.innerHTML = "<span>Nenhum QR Code ativo.</span>";
    }
}

async function whatsappFetch(path, options = {}) {
    const res = await fetch(`${API_BASE}/api/whatsapp${path}`, {
        ...options,
        headers: {
            ...whatsappAuthHeaders(),
            ...(options.headers || {}),
        },
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || data.error || "Falha ao consultar WhatsApp.");
    }
    return res.json();
}

async function loadWhatsappQr() {
    try {
        const data = await whatsappFetch("/qrcode");
        const qrBox = document.getElementById("wa-qr-box");
        if (!qrBox) return;
        if (data.qrImage) {
            qrBox.innerHTML = `<img src="${data.qrImage}" alt="QR Code WhatsApp"><small>Gerado em ${whatsappFormatDate(data.qrUpdatedAt)}</small>`;
        } else {
            qrBox.innerHTML = "<span>Aguardando novo QR Code...</span>";
        }
    } catch (error) {
        console.error("Erro ao carregar QR:", error);
    }
}

async function loadWhatsappLogs() {
    try {
        const logs = await whatsappFetch("/logs");
        const list = document.getElementById("wa-log-list");
        if (!list) return;
        if (!logs.length) {
            list.innerHTML = `<div class="wa-log-empty">Nenhum evento registrado ainda.</div>`;
            return;
        }
        list.innerHTML = logs.map(item => `
            <div class="wa-log-item">
                <strong>${item.event_type}</strong>
                <span>${item.status || "-"} - ${whatsappFormatDate(item.created_at)}</span>
            </div>
        `).join("");
    } catch (error) {
        console.error("Erro ao carregar logs WhatsApp:", error);
    }
}

async function refreshWhatsappStatus() {
    try {
        const status = await whatsappFetch("/status");
        updateWhatsappStatus(status);
        await loadWhatsappLogs();
    } catch (error) {
        updateWhatsappStatus({ status: "disconnected", disconnectReason: error.message, updatedAt: new Date().toISOString() });
    }
}

async function runWhatsappAction(action, successMessage) {
    try {
        const status = await whatsappFetch(`/${action}`, { method: "POST" });
        updateWhatsappStatus(status);
        await loadWhatsappLogs();
        if (typeof showToast === "function") showToast("WhatsApp", successMessage, "success");
    } catch (error) {
        if (typeof showToast === "function") showToast("Erro no WhatsApp", error.message, "error");
    }
}

function bindWhatsappControls() {
    if (whatsappControlsBound) return;
    whatsappControlsBound = true;
    document.getElementById("btn-wa-refresh")?.addEventListener("click", refreshWhatsappStatus);
    document.getElementById("btn-wa-connect")?.addEventListener("click", () => runWhatsappAction("connect", "Conexao solicitada."));
    document.getElementById("btn-wa-reconnect")?.addEventListener("click", () => runWhatsappAction("reconnect", "Reconexao solicitada."));
    document.getElementById("btn-wa-disconnect")?.addEventListener("click", () => runWhatsappAction("disconnect", "Sessao desconectada."));
    document.getElementById("btn-wa-logout")?.addEventListener("click", () => {
        if (!confirm("Isso remove a sessao atual e exige novo QR Code. Continuar?")) return;
        runWhatsappAction("logout", "Sessao removida. Escaneie o novo QR Code.");
    });
}

function startWhatsappEvents() {
    const token = localStorage.getItem("access_token");
    if (!token || whatsappEventSource) return;
    whatsappEventSource = new EventSource(`${API_BASE}/api/whatsapp/events?token=${encodeURIComponent(token)}`);
    whatsappEventSource.onmessage = (event) => {
        try {
            updateWhatsappStatus(JSON.parse(event.data));
        } catch (_) {}
    };
    whatsappEventSource.onerror = () => {
        whatsappEventSource.close();
        whatsappEventSource = null;
        setTimeout(startWhatsappEvents, 5000);
    };
}

async function renderWhatsappPanel() {
    if (whatsappRendering) return;
    whatsappRendering = true;
    bindWhatsappControls();
    startWhatsappEvents();
    await refreshWhatsappStatus();
    whatsappRendering = false;
}
