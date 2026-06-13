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
    const adminAvatarContainer = document.getElementById("admin-avatar-container");
    const adminAvatarInput = document.getElementById("admin-avatar-input");
    const adminAvatarPreview = document.getElementById("admin-avatar-preview");
    const adminAvatarPlaceholder = document.getElementById("admin-avatar-placeholder");
    let selectedAvatarFile = null;

    if (adminAvatarContainer && adminAvatarInput) {
        // Drag and Drop
        adminAvatarContainer.addEventListener("dragover", (e) => {
            e.preventDefault();
            adminAvatarContainer.classList.add("dragover");
        });
        adminAvatarContainer.addEventListener("dragleave", () => {
            adminAvatarContainer.classList.remove("dragover");
        });
        adminAvatarContainer.addEventListener("drop", (e) => {
            e.preventDefault();
            adminAvatarContainer.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleAvatarSelection(e.dataTransfer.files[0]);
            }
        });
        adminAvatarContainer.addEventListener("click", () => {
            adminAvatarInput.click();
        });
        adminAvatarInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files[0]) {
                handleAvatarSelection(e.target.files[0]);
            }
        });

        function handleAvatarSelection(file) {
            if (!file.type.startsWith("image/")) {
                alert("Por favor, selecione uma imagem.");
                return;
            }
            selectedAvatarFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                adminAvatarPreview.src = e.target.result;
                adminAvatarPreview.style.display = "block";
                adminAvatarPlaceholder.style.display = "none";
            };
            reader.readAsDataURL(file);
        }
    }

    function resetAdminAvatar() {
        selectedAvatarFile = null;
        if (adminAvatarInput) adminAvatarInput.value = "";
        if (adminAvatarPreview) {
            adminAvatarPreview.src = "";
            adminAvatarPreview.style.display = "none";
        }
        if (adminAvatarPlaceholder) {
            adminAvatarPlaceholder.style.display = "block";
        }
    }

    btnAddAdminModal.addEventListener("click", () => {
        document.getElementById("admin-id").value = "";
        document.getElementById("admin-modal-title").innerText = "Adicionar Administrador";
        formAddAdmin.reset();
        resetAdminAvatar();
        modalAdmin.classList.add("active");
    });
    const closeAdminModal = () => {
        modalAdmin.classList.remove("active");
        formAddAdmin.reset();
        resetAdminAvatar();
        document.getElementById("admin-id").value = "";
    };
    btnCloseAdminModal.addEventListener("click", closeAdminModal);
    btnCancelAdminModal.addEventListener("click", closeAdminModal);

    formAddAdmin.addEventListener("submit", async (e) => {
        e.preventDefault();

        const id = document.getElementById("admin-id").value;
        const name = document.getElementById("admin-name").value.trim();
        const email = document.getElementById("admin-email").value.trim();
        const role = document.getElementById("admin-role").value;
        const passwordInput = document.getElementById("admin-password");
        const password = passwordInput ? passwordInput.value.trim() : "";

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
                
                // Upload do Avatar se houver
                if (selectedAvatarFile) {
                    const formData = new FormData();
                    formData.append("file", selectedAvatarFile);
                    try {
                        const avatarRes = await fetch(`${API_BASE}/api/admins/${savedAdmin.id}/avatar`, {
                            method: "POST",
                            body: formData
                        });
                        if (avatarRes.ok) {
                            const updatedAdmin = await avatarRes.json();
                            Object.assign(savedAdmin, updatedAdmin);
                        }
                    } catch(e) {
                        console.error("Erro no upload do avatar", e);
                    }
                }

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