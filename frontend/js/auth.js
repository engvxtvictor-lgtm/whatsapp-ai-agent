// 0. AUTENTICAÇÃO / LOGIN
const loginScreen = document.getElementById("login-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const btnLogout = document.getElementById("btn-logout");

function checkAuth() {
    const token = localStorage.getItem("access_token");
    if (token) {
        loginScreen.classList.add("hidden");
    } else {
        loginScreen.classList.remove("hidden");
    }
}

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value.trim();
    try {
        const res = await fetch("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        if (!res.ok) throw new Error("Credenciais inválidas");
        const data = await res.json();
        localStorage.setItem("access_token", data.access_token);
        loginError.style.display = "none";
        loginScreen.classList.add("hidden");
    } catch (err) {
        loginError.style.display = "block";
        console.error(err);
    }
});

btnLogout.addEventListener("click", (e) => {
    e.preventDefault();
    localStorage.removeItem("access_token");
    checkAuth();
});

checkAuth();