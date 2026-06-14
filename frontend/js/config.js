// Configuração global da API — importado por todos os módulos JS do frontend
// Em produção, usa URL relativa para que o Nginx faça o proxy para o backend.
// Em desenvolvimento local (sem Nginx), altere para "http://localhost:8000".
const API_BASE = window.location.port === "5178" ? "http://localhost:8000" : "";
