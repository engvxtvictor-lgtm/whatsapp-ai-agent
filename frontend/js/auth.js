// 0. AUTENTICAÇÃO / LOGIN
document.addEventListener("DOMContentLoaded", () => {
    const loginScreen = document.getElementById("login-screen");
    const loginForm = document.getElementById("login-form");
    const loginError = document.getElementById("login-error");
    const btnLogout = document.getElementById("btn-logout");

    function checkAuth() {
        const token = localStorage.getItem("access_token");
        if (token) {
            if (loginScreen) loginScreen.classList.add("hidden");
            // Decodifica o payload do JWT para recuperar o admin_email se necessário
            if (!localStorage.getItem("admin_email")) {
                try {
                    const base64Url = token.split('.')[1];
                    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                    const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }).join(''));
                    const payload = JSON.parse(jsonPayload);
                    if (payload && payload.sub) {
                        localStorage.setItem("admin_email", payload.sub);
                    }
                } catch (e) {
                    console.error("Erro ao decodificar token:", e);
                }
            }
        } else {
            if (loginScreen) loginScreen.classList.remove("hidden");
        }
    }

    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById("login-email");
            const passwordInput = document.getElementById("login-password");
            const email = emailInput ? emailInput.value.trim() : "";
            const password = passwordInput ? passwordInput.value.trim() : "";
            try {
                const res = await fetch(`${API_BASE}/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password })
                });
                if (!res.ok) {
                    let errMsg = "Credenciais inválidas";
                    try {
                        const errData = await res.json();
                        if (errData && errData.detail) {
                            errMsg = errData.detail;
                        }
                    } catch (_) {}
                    throw new Error(errMsg);
                }
                const data = await res.json();
                localStorage.setItem("access_token", data.access_token);
                localStorage.setItem("admin_email", email);
                if (loginError) loginError.style.display = "none";
                if (loginScreen) loginScreen.classList.add("hidden");
                
                // Recarrega a página ou chama loadData() para atualizar os dados após login
                if (typeof loadData === "function") {
                    loadData();
                } else {
                    window.location.reload();
                }
            } catch (err) {
                if (loginError) {
                    loginError.textContent = err.message || "Erro ao fazer login. Tente novamente!";
                    loginError.style.display = "block";
                }
                console.error(err);
            }
        });
    }

    if (btnLogout) {
        btnLogout.addEventListener("click", (e) => {
            e.preventDefault();
            localStorage.removeItem("access_token");
            localStorage.removeItem("admin_email");
            checkAuth();
        });
    }

    checkAuth();
});