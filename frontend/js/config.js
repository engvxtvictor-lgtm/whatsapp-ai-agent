// Permite configurar a URL do backend de forma dinâmica se necessário (ex: fora do proxy Nginx).
// Fallback padrão: URL relativa para comunicação via Nginx proxy.
const API_BASE = window.API_BASE_URL || localStorage.getItem("API_BASE_URL") || "";
