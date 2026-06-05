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
            const response = await fetch(`${API_BASE}/api/clients`, {
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
    btnAddAdminModal.addEventListener("click", () => {
        document.getElementById("admin-id").value = "";
        document.getElementById("admin-modal-title").innerText = "Adicionar Administrador";
        formAddAdmin.reset();
        modalAdmin.classList.add("active");
    });
    const closeAdminModal = () => {
        modalAdmin.classList.remove("active");
        formAddAdmin.reset();
        document.getElementById("admin-id").value = "";
    };
    btnCloseAdminModal.addEventListener("click", closeAdminModal);
    btnCancelAdminModal.addEventListener("click", closeAdminModal);

    formAddAdmin.addEventListener("submit", async (e) => {
        e.preventDefault();

        const id = document.getElementById("admin-id").value;
        const name = document.getElementById("admin-name").value;
        const email = document.getElementById("admin-email").value;
        const role = document.getElementById("admin-role").value;
        const passwordInput = document.getElementById("admin-password");
        const password = passwordInput ? passwordInput.value : "";

        const payload = { name, email, role };
        if (password) {
            payload.password = password;
        }
        const isEdit = !!id;

        try {
            const url = isEdit ? `${API_BASE}/api/admins/${id}` : `${API_BASE}/api/admins`;
            const method = isEdit ? "PUT" : "POST";

            const response = await fetch(url, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const savedAdmin = await response.json();
                if (isEdit) {
                    const index = allAdmins.findIndex(a => a.id == id);
                    if (index !== -1) allAdmins[index] = savedAdmin;
                } else {
                    allAdmins.unshift(savedAdmin);
                }
                renderAdmins();
                closeAdminModal();
            } else {
                const errorText = await response.text();
                alert(`Erro ao salvar administrador. Status: ${response.status}\nDetalhes: ${errorText}`);
            }
        } catch (error) {
            console.error("Erro:", error);
            alert(`Erro na requisição: ${error.message}`);
        }
    });