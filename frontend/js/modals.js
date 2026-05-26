// 6. GERENCIAMENTO DE MODAIS E CADASTROS
    // Novo Cliente Modal
    const upsellSuccessSelect = document.getElementById("client-upsell-success");
    const groupUpsellService = document.getElementById("group-upsell-service");
    
    upsellSuccessSelect.addEventListener("change", () => {
        groupUpsellService.style.display = upsellSuccessSelect.value === "true" ? "block" : "none";
    });

    btnAddClientModal.addEventListener("click", () => modalClient.classList.add("active"));
    btnCloseClientModal.addEventListener("click", () => {
        modalClient.classList.remove("active");
        formAddClient.reset();
        groupUpsellService.style.display = "none";
    });
    btnCancelClientModal.addEventListener("click", () => {
        modalClient.classList.remove("active");
        formAddClient.reset();
        groupUpsellService.style.display = "none";
    });

    formAddClient.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const name = document.getElementById("client-name").value;
        const cpf = document.getElementById("client-cpf").value;
        const phone = document.getElementById("client-phone").value;
        const service = document.getElementById("client-service").value;
        const source = document.getElementById("client-source").value;
        
        const appointment_date = document.getElementById("client-appointment-date").value || null;
        const upsell_success = document.getElementById("client-upsell-success").value === "true";
        const upsell_service = upsell_success ? (document.getElementById("client-upsell-service").value || null) : null;

        const payload = { 
            name, 
            cpf, 
            phone, 
            service, 
            source,
            appointment_date,
            upsell_success,
            upsell_service
        };

        try {
            const response = await fetch("/api/clients", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const newClient = await response.json();
                allClients.unshift(newClient); // Adiciona no início da lista
                renderClients();
                formAddClient.reset();
                groupUpsellService.style.display = "none";
                modalClient.classList.remove("active");
            } else {
                alert("Erro ao cadastrar paciente.");
            }
        } catch (error) {
            console.error("Erro cadastro cliente:", error);
            alert("Erro de conexão com o servidor.");
        }
    });

    // Novo Administrador Modal
    btnAddAdminModal.addEventListener("click", () => modalAdmin.classList.add("active"));
    btnCloseAdminModal.addEventListener("click", () => modalAdmin.classList.remove("active"));
    btnCancelAdminModal.addEventListener("click", () => modalAdmin.classList.remove("active"));

    formAddAdmin.addEventListener("submit", async (e) => {
        e.preventDefault();

        const name = document.getElementById("admin-name").value;
        const email = document.getElementById("admin-email").value;
        const role = document.getElementById("admin-role").value;

        const payload = { name, email, role };

        try {
            const response = await fetch("/api/admins", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const newAdmin = await response.json();
                allAdmins.unshift(newAdmin);
                renderAdmins();
                formAddAdmin.reset();
                modalAdmin.classList.remove("active");
            } else {
                alert("Erro ao cadastrar administrador.");
            }
        } catch (error) {
            console.error("Erro cadastro admin:", error);
            alert("Erro de conexão com o servidor.");
        }
    });