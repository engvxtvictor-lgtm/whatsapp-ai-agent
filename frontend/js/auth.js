// 0. AUTENTICAÇÃO / LOGIN
const loginScreen = document.getElementById("login-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const btnLogout = document.getElementById("btn-logout");

function checkAuth() {
    const token = localStorage.getItem("access_token");
    if (token) {
        loginScreen.classList.add("hidden");
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
        loginScreen.classList.remove("hidden");
    }
}

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value.trim();
    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        if (!res.ok) {
            let errorMsg = "Credenciais inválidas";
            try {
                const errorData = await res.json();
                if (errorData && errorData.detail) {
                    errorMsg = errorData.detail;
                }
            } catch (e) {}
            throw new Error(errorMsg);
        }
        const data = await res.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("admin_email", email);
        loginError.style.display = "none";
        loginScreen.classList.add("hidden");
    } catch (err) {
        loginError.textContent = err.message;
        loginError.style.display = "block";
        console.error(err);
    }
});

btnLogout.addEventListener("click", (e) => {
    e.preventDefault();
    localStorage.removeItem("access_token");
    localStorage.removeItem("admin_email");
    checkAuth();
});

checkAuth();