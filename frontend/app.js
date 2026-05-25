// JavaScript - Painel de Controle Clínica Lúmina

document.addEventListener("DOMContentLoaded", () => {
    // 0. AUTENTICAÇÃO / LOGIN
    const loginScreen = document.getElementById("login-screen");
    const loginForm = document.getElementById("login-form");
    const loginError = document.getElementById("login-error");
    const btnLogout = document.getElementById("btn-logout");

    function checkAuth() {
        const isLogged = localStorage.getItem("admin_logged") === "true";
        if (isLogged) {
            loginScreen.classList.add("hidden");
        } else {
            loginScreen.classList.remove("hidden");
        }
    }

    loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const email = document.getElementById("login-email").value.trim();
        const password = document.getElementById("login-password").value.trim();

        if (email === "admin@lumina.com" && password === "admin123") {
            localStorage.setItem("admin_logged", "true");
            loginError.style.display = "none";
            loginScreen.classList.add("hidden");
        } else {
            loginError.style.display = "block";
        }
    });

    btnLogout.addEventListener("click", (e) => {
        e.preventDefault();
        localStorage.removeItem("admin_logged");
        checkAuth();
    });

    checkAuth();

    // Estado Global do Frontend
    let allClients = [];
    let allAdmins = [];
    let allExams = [];
    let allSlots = [];
    const selectedClients = new Set();
    const activeHumanRequests = new Set();

    // Referências do DOM
    const tabNavItems = document.querySelectorAll(".nav-item");
    const tabPanels = document.querySelectorAll(".tab-panel");
    const pageTitle = document.getElementById("page-title");
    const pageDescription = document.getElementById("page-description");

    const clientsGrid = document.getElementById("clients-grid");
    const adminsGrid = document.getElementById("admins-grid");

    // Inputs de Filtros e Busca
    const clientSearchInput = document.getElementById("client-search");
    const filterServiceSelect = document.getElementById("filter-service");
    const filterSourceSelect = document.getElementById("filter-source");

    // Métricas
    const metricTotalClients = document.getElementById("metric-total-clients");
    const metricWaClients = document.getElementById("metric-wa-clients");
    const metricIgClients = document.getElementById("metric-ig-clients");
    const metricSelectedClients = document.getElementById("metric-selected-clients");

    // Seleção em lote bar
    const batchActionBar = document.querySelector(".batch-action-bar");
    const batchSelectionText = document.getElementById("batch-selection-text");
    const btnSelectAll = document.getElementById("btn-select-all");
    const btnClearSelection = document.getElementById("btn-clear-selection");
    const btnSendCampaignFromSelection = document.getElementById("btn-send-campaign-from-selection");

    // Modais
    const modalClient = document.getElementById("modal-client");
    const modalAdmin = document.getElementById("modal-admin");
    const modalSlot = document.getElementById("modal-slot");
    const btnAddClientModal = document.getElementById("btn-add-client-modal");
    const btnAddAdminModal = document.getElementById("btn-add-admin-modal");
    const btnAddSlotModal = document.getElementById("btn-add-slot-modal");

    // Slots refs
    const btnCloseSlotModal = document.getElementById("btn-close-slot-modal");
    const btnCancelSlotModal = document.getElementById("btn-cancel-slot-modal");
    const formAddSlot = document.getElementById("form-add-slot");
    const slotsTableBody = document.getElementById("slots-table-body");
    const slotSearchInput = document.getElementById("slot-search");

    // Fechar Modais
    const btnCloseClientModal = document.getElementById("btn-close-client-modal");
    const btnCancelClientModal = document.getElementById("btn-cancel-client-modal");
    const btnCloseAdminModal = document.getElementById("btn-close-admin-modal");
    const btnCancelAdminModal = document.getElementById("btn-cancel-admin-modal");

    // Formulários
    const formAddClient = document.getElementById("form-add-client");
    const formAddAdmin = document.getElementById("form-add-admin");

    // Painel de Campanha
    const campaignMessageTextarea = document.getElementById("campaign-message");
    const btnSubmitCampaign = document.getElementById("btn-submit-campaign");
    const quickTemplatePills = document.querySelectorAll(".template-pill");
    const campaignSelectedCountTitle = document.getElementById("campaign-selected-count-title");
    const campaignSelectedCountDesc = document.getElementById("campaign-selected-count-desc");

    // Helper to normalize and get Category HSL Badge Class
    function getCategoryClass(category) {
        if (!category) return 'badge-cat-none';
        const normalized = category.toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "") // remove accents
            .replace(/\s+/g, '-') // spaces to hyphen
            .replace(/[^a-z0-9\-]/g, ''); // keep alphanumeric and hyphen
        return `badge-cat-${normalized}`;
    }

    // 1. NAVEGAÇÃO DE ABAS
    tabNavItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetTab = item.getAttribute("data-tab");

            // Ativa navegação lateral
            tabNavItems.forEach(nav => nav.classList.remove("active"));
            item.classList.add("active");

            // Mostra o painel correto
            tabPanels.forEach(panel => {
                panel.classList.remove("active");
                if (panel.id === `tab-${targetTab}`) {
                    panel.classList.add("active");
                }
            });

            // Atualiza Título e Descrição da página
            updateHeaderDetails(targetTab);
        });
    });

    function updateHeaderDetails(tab) {
        if (tab === "clients") {
            pageTitle.innerText = "Clientes & Fila";
            pageDescription.innerText = "Gerenciamento e controle de mensagens de pacientes da Clínica Lúmina.";
        } else if (tab === "admins") {
            pageTitle.innerText = "Administradores";
            pageDescription.innerText = "Gerenciamento dos profissionais de saúde e atendentes da Lúmina.";
        } else if (tab === "campaigns") {
            pageTitle.innerText = "Campanhas & Follow-Up";
            pageDescription.innerText = "Dispare mensagens personalizadas e automatize lembretes pós-consulta.";
            updateCampaignSelectionPanel();
        } else if (tab === "exams") {
            pageTitle.innerText = "Tabela de Exames & Valores";
            pageDescription.innerText = "Tabela de exames e procedimentos oficiais da Clínica Lúmina para 2026.";
            renderExams();
        } else if (tab === "schedule") {
            pageTitle.innerText = "Grade de Horários Disponíveis";
            pageDescription.innerText = "Configure os dias e horários em que a clínica atende para que o agente virtual possa oferecer aos pacientes.";
            renderSlots();
        }
    }

    // 2. BUSCAR E FILTRAR PACIENTES (CLIENTES)
    function renderClients() {
        const query = clientSearchInput.value.toLowerCase().trim();
        const serviceFilter = filterServiceSelect.value;
        const sourceFilter = filterSourceSelect.value;

        // Filtra a lista
        const filtered = allClients.filter(client => {
            const matchesSearch = client.name.toLowerCase().includes(query) ||
                                  client.cpf.includes(query) ||
                                  client.phone.includes(query);
            const matchesService = serviceFilter === "" || client.service === serviceFilter;
            const matchesSource = sourceFilter === "" || client.source === sourceFilter;

            return matchesSearch && matchesService && matchesSource;
        });

        // Limpa grid
        clientsGrid.innerHTML = "";

        if (filtered.length === 0) {
            clientsGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; padding: 50px; text-align: center; background: rgba(255,255,255,0.5); border-radius: 12px; border: 1px dashed var(--border-gold-soft);">
                    <i class="fa-solid fa-folder-open" style="font-size: 40px; color: var(--gold-primary); margin-bottom: 15px;"></i>
                    <p style="font-weight: 500; color: var(--charcoal-text)">Nenhum paciente encontrado para os filtros ativos.</p>
                </div>
            `;
            return;
        }

        // Renderiza cada card
        filtered.forEach(client => {
            const isSelected = selectedClients.has(client.id);

            const card = document.createElement("div");
            card.className = `client-card ${isSelected ? 'selected' : ''} ${client.needs_human ? 'needs-human' : ''}`;
            card.setAttribute("data-id", client.id);

            // Determina Ícone e Cor do Canal
            const isWA = client.source === "whatsapp";
            const channelBadgeClass = isWA ? "badge-wa" : "badge-ig";
            const channelIcon = isWA ? "fa-brands fa-whatsapp" : "fa-brands fa-instagram";
            const channelLabel = isWA ? "WhatsApp" : "Instagram";

            const upsellBadge = client.upsell_success 
                ? `<span class="badge badge-upsell"><i class="fa-solid fa-star"></i> Upsell: ${client.upsell_service || 'Sim'}</span>`
                : `<span class="badge badge-no-upsell">Sem Upsell</span>`;

            let appointmentText = client.appointment_date;
            if (client.slot_date) {
                const parts = client.slot_date.split("-");
                if (parts.length === 3) {
                    const dateFormatted = `${parts[2]}/${parts[1]}/${parts[0]}`;
                    const timeText = client.slot_time || "";
                    appointmentText = `${dateFormatted}${timeText ? ' às ' + timeText : ''}`;
                }
            }
            const appointmentBadge = appointmentText
                ? `<div class="client-appointment-badge"><i class="fa-regular fa-calendar-check"></i> ${appointmentText}</div>`
                : `<div class="client-appointment-badge" style="color: #c5a880; border-color: rgba(197,168,128,0.2);"><i class="fa-regular fa-calendar-times"></i> Sem agendamento</div>`;

            const statusLabels = {
                pending: "Pendente",
                confirmed: "Confirmado",
                cancelled: "Recusado"
            };
            const statusClass = `status-${client.status || 'pending'}`;
            const statusLabel = statusLabels[client.status || 'pending'] || "Pendente";
            const statusBadgeHtml = `<span class="client-status-badge ${statusClass}">${statusLabel}</span>`;

            let actionsHtml = "";
            if ((client.status || "pending") === "pending" && client.appointment_date) {
                actionsHtml = `
                    <div class="client-actions">
                        <button class="btn-action-confirm" title="Confirmar Agendamento"><i class="fa-solid fa-check"></i> Aceitar</button>
                        <button class="btn-action-cancel" title="Recusar Agendamento"><i class="fa-solid fa-xmark"></i> Recusar</button>
                    </div>
                `;
            }

            const iaToggleHtml = `
                <div class="client-ia-toggle">
                    <span class="toggle-label"><i class="fa-solid fa-robot"></i> IA Comercial</span>
                    <label class="switch">
                        <input type="checkbox" class="ia-toggle-checkbox" ${client.ai_active ? 'checked' : ''}>
                        <span class="slider"></span>
                    </label>
                </div>
            `;

            // Category badge
            const categoryBadgeHtml = client.exam_category
                ? `<span class="badge-category ${getCategoryClass(client.exam_category)}">
                       <i class="fa-solid fa-tag"></i> ${client.exam_category}
                   </span>`
                : '';

            card.innerHTML = `
                <input type="checkbox" class="client-card-select" ${isSelected ? 'checked' : ''}>
                ${statusBadgeHtml}
                <div class="client-avatar-container">
                    <img src="${client.profile_pic || 'https://api.dicebear.com/7.x/adventurer/svg?seed=Lumina'}" alt="${client.name}" class="client-avatar">
                </div>
                <h4 class="client-name">${client.name}</h4>
                <p class="client-meta"><strong>CPF:</strong> ${client.cpf}</p>
                <p class="client-meta"><strong>Tel:</strong> ${client.phone}</p>
                
                <div class="client-badges">
                    <span class="badge ${channelBadgeClass}">
                        <i class="${channelIcon}"></i> ${channelLabel}
                    </span>
                    <span class="badge badge-service">
                        ${client.service}
                    </span>
                    ${categoryBadgeHtml}
                    ${upsellBadge}
                </div>
                ${appointmentBadge}
                ${actionsHtml}
                ${iaToggleHtml}
            `;

            // Clique no Checkbox
            const checkbox = card.querySelector(".client-card-select");
            checkbox.addEventListener("click", (e) => {
                e.stopPropagation(); // Evita triggar o clique do card completo
                toggleClientSelection(client.id, checkbox.checked);
            });

            // Clique no toggle da IA
            const iaCheckbox = card.querySelector(".ia-toggle-checkbox");
            iaCheckbox.addEventListener("click", async (e) => {
                e.stopPropagation(); // Evita selecionar o card
                const checked = iaCheckbox.checked;
                try {
                    const response = await fetch(`/api/sessions/${client.phone}/toggle-ai`, {
                        method: "PUT"
                    });
                    if (response.ok) {
                        const data = await response.json();
                        client.ai_active = data.ai_active;
                    } else {
                        iaCheckbox.checked = !checked;
                        alert("Falha ao alternar status da IA Comercial.");
                    }
                } catch (error) {
                    console.error("Erro toggle AI:", error);
                    iaCheckbox.checked = !checked;
                    alert("Erro de conexao com o servidor.");
                }
            });

            // Acoes de confirmar/recusar agendamento
            if ((client.status || "pending") === "pending" && client.appointment_date) {
                const btnConfirm = card.querySelector(".btn-action-confirm");
                const btnCancel = card.querySelector(".btn-action-cancel");

                btnConfirm.addEventListener("click", async (e) => {
                    e.stopPropagation(); // Evita selecionar o card
                    const loggedAdminName = "Dra. Ana Souza"; // admin padrao
                    btnConfirm.disabled = true;
                    btnConfirm.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Aceitando...`;

                    try {
                        const response = await fetch(`/api/clients/${client.id}/confirm`, {
                            method: "PUT",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ admin_name: loggedAdminName })
                        });
                        if (response.ok) {
                            client.status = "confirmed";
                            loadData(); // Recarrega lista
                        } else {
                            alert("Falha ao confirmar consulta.");
                            btnConfirm.disabled = false;
                            btnConfirm.innerHTML = `<i class="fa-solid fa-check"></i> Aceitar`;
                        }
                    } catch (error) {
                        console.error("Erro confirmar consulta:", error);
                        alert("Erro de conexao com o servidor.");
                        btnConfirm.disabled = false;
                        btnConfirm.innerHTML = `<i class="fa-solid fa-check"></i> Aceitar`;
                    }
                });

                btnCancel.addEventListener("click", async (e) => {
                    e.stopPropagation(); // Evita selecionar o card
                    btnCancel.disabled = true;
                    btnCancel.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Recusando...`;

                    try {
                        const response = await fetch(`/api/clients/${client.id}/cancel`, {
                            method: "PUT"
                        });
                        if (response.ok) {
                            client.status = "cancelled";
                            loadData(); // Recarrega lista
                        } else {
                            alert("Falha ao recusar consulta.");
                            btnCancel.disabled = false;
                            btnCancel.innerHTML = `<i class="fa-solid fa-xmark"></i> Recusar`;
                        }
                    } catch (error) {
                        console.error("Erro recusar consulta:", error);
                        alert("Erro de conexao com o servidor.");
                        btnCancel.disabled = false;
                        btnCancel.innerHTML = `<i class="fa-solid fa-xmark"></i> Recusar`;
                    }
                });
            }

            // Clique no Card completo (alterna selecao ou abre wa.me se precisar de suporte)
            card.addEventListener("click", async (e) => {
                if (e.target.closest('.client-ia-toggle') || e.target.closest('.client-actions') || e.target.closest('.client-card-select')) {
                    return;
                }
                
                if (client.needs_human) {
                    // Open wa.me link directly
                    window.open(`https://wa.me/${client.phone}`, "_blank");
                    
                    // Resolve needs_human on the backend
                    try {
                        const res = await fetch(`/api/clients/${client.id}/resolve-human`, {
                            method: "PUT"
                        });
                        if (res.ok) {
                            client.needs_human = false;
                            activeHumanRequests.delete(client.id);
                            renderClients(); // Re-render to update classes and badges
                        }
                    } catch (err) {
                        console.error("Erro ao resolver suporte humano:", err);
                    }
                    return;
                }

                const newStatus = !selectedClients.has(client.id);
                checkbox.checked = newStatus;
                toggleClientSelection(client.id, newStatus);
            });

            clientsGrid.appendChild(card);
        });

        updateMetrics();
    }

    function toggleClientSelection(id, select) {
        const card = document.querySelector(`.client-card[data-id="${id}"]`);
        if (select) {
            selectedClients.add(id);
            if (card) card.classList.add("selected");
        } else {
            selectedClients.delete(id);
            if (card) card.classList.remove("selected");
        }
        updateMetrics();
        updateBatchActionBar();
    }

    // 3. SELEÇÃO EM LOTE E ATUALIZAÇÃO DE MÉTRICAS
    function updateMetrics() {
        metricTotalClients.innerText = allClients.length;
        metricWaClients.innerText = allClients.filter(c => c.source === "whatsapp").length;
        metricIgClients.innerText = allClients.filter(c => c.source === "instagram").length;
        metricSelectedClients.innerText = selectedClients.size;
    }

    function updateBatchActionBar() {
        if (selectedClients.size > 0) {
            batchSelectionText.innerText = `${selectedClients.size} paciente(s) selecionado(s)`;
            batchActionBar.style.display = "flex";
        } else {
            batchActionBar.style.display = "none";
        }
    }

    btnSelectAll.addEventListener("click", () => {
        // Seleciona todos os atualmente visíveis/filtrados
        const query = clientSearchInput.value.toLowerCase().trim();
        const serviceFilter = filterServiceSelect.value;
        const sourceFilter = filterSourceSelect.value;

        allClients.forEach(client => {
            const matchesSearch = client.name.toLowerCase().includes(query) ||
                                  client.cpf.includes(query) ||
                                  client.phone.includes(query);
            const matchesService = serviceFilter === "" || client.service === serviceFilter;
            const matchesSource = sourceFilter === "" || client.source === sourceFilter;

            if (matchesSearch && matchesService && matchesSource) {
                selectedClients.add(client.id);
                const card = document.querySelector(`.client-card[data-id="${client.id}"]`);
                if (card) {
                    card.classList.add("selected");
                    card.querySelector(".client-card-select").checked = true;
                }
            }
        });
        updateMetrics();
        updateBatchActionBar();
    });

    btnClearSelection.addEventListener("click", () => {
        selectedClients.clear();
        document.querySelectorAll(".client-card").forEach(card => {
            card.classList.remove("selected");
            card.querySelector(".client-card-select").checked = false;
        });
        updateMetrics();
        updateBatchActionBar();
    });

    // Direciona da seleção para a aba de Campanhas
    btnSendCampaignFromSelection.addEventListener("click", () => {
        const itemCampaign = document.querySelector('.nav-item[data-tab="campaigns"]');
        if (itemCampaign) itemCampaign.click();
    });

    // Escuta filtros
    clientSearchInput.addEventListener("input", renderClients);
    filterServiceSelect.addEventListener("change", renderClients);
    filterSourceSelect.addEventListener("change", renderClients);

    // 4. RENDERIZAR ADMINISTRADORES
    function renderAdmins() {
        adminsGrid.innerHTML = "";
        
        allAdmins.forEach(admin => {
            const card = document.createElement("div");
            card.className = "admin-card";
            card.innerHTML = `
                <img src="${admin.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=Lumina'}" alt="${admin.name}" class="admin-avatar">
                <h4 class="admin-name">${admin.name}</h4>
                <p class="admin-email">${admin.email}</p>
                <span class="admin-role-badge">${admin.role}</span>
            `;
            adminsGrid.appendChild(card);
        });
    }

    // 5. ENVIAR CAMPANHAS E TEMPLATES
    quickTemplatePills.forEach(pill => {
        pill.addEventListener("click", () => {
            const text = pill.getAttribute("data-msg");
            campaignMessageTextarea.value = text;
            validateCampaignForm();
        });
    });

    campaignMessageTextarea.addEventListener("input", validateCampaignForm);

    function validateCampaignForm() {
        const hasText = campaignMessageTextarea.value.trim().length > 0;
        const hasSelection = selectedClients.size > 0;
        btnSubmitCampaign.disabled = !(hasText && hasSelection);
    }

    function updateCampaignSelectionPanel() {
        const size = selectedClients.size;
        validateCampaignForm();

        if (size > 0) {
            campaignSelectedCountTitle.innerText = `${size} Paciente(s) Selecionado(s)`;
            campaignSelectedCountDesc.innerHTML = `A campanha será disparada individualmente no WhatsApp de cada um dos <strong>${size}</strong> pacientes selecionados.`;
            campaignSelectedCountTitle.parentElement.parentElement.classList.remove("card-alert");
            campaignSelectedCountTitle.parentElement.parentElement.style.background = "rgba(197, 168, 128, 0.12)";
            campaignSelectedCountTitle.parentElement.parentElement.style.borderColor = "var(--gold-primary)";
        } else {
            campaignSelectedCountTitle.innerText = "Nenhum cliente selecionado";
            campaignSelectedCountDesc.innerText = "Volte à aba \"Clientes & Fila\" e marque os pacientes que devem receber esta mensagem.";
            campaignSelectedCountTitle.parentElement.parentElement.classList.add("card-alert");
            campaignSelectedCountTitle.parentElement.parentElement.style.background = "";
            campaignSelectedCountTitle.parentElement.parentElement.style.borderColor = "";
        }
    }

    btnSubmitCampaign.addEventListener("click", async () => {
        const message = campaignMessageTextarea.value;
        const clientIds = Array.from(selectedClients);

        btnSubmitCampaign.disabled = true;
        btnSubmitCampaign.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Disparando Mensagens...`;

        try {
            const response = await fetch("/api/campaigns", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    client_ids: clientIds,
                    message: message
                })
            });

            if (response.ok) {
                alert(`Sucesso! Campanha de WhatsApp programada com sucesso para ${clientIds.length} pacientes.`);
                campaignMessageTextarea.value = "";
                selectedClients.clear();
                document.querySelectorAll(".client-card").forEach(c => {
                    c.classList.remove("selected");
                    const chk = c.querySelector(".client-card-select");
                    if (chk) chk.checked = false;
                });
                updateMetrics();
                updateBatchActionBar();
                updateCampaignSelectionPanel();
            } else {
                alert("Falha ao disparar campanha. Verifique os dados.");
            }
        } catch (error) {
            console.error("Erro campanha:", error);
            alert("Erro de conexão ao disparar a campanha.");
        } finally {
            btnSubmitCampaign.innerHTML = `<i class="fa-solid fa-rocket"></i> Disparar Campanha de WhatsApp`;
            validateCampaignForm();
        }
    });

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

    // 7. GERENCIAMENTO DE AUTOMACÕES DE FOLLOW-UP
    const followupRulesContainer = document.getElementById("follow-up-rules-container");
    const modalFollowup = document.getElementById("modal-followup");
    const btnAddFollowupModal = document.getElementById("btn-add-followup-modal");
    const btnCloseFollowupModal = document.getElementById("btn-close-followup-modal");
    const btnCancelFollowupModal = document.getElementById("btn-cancel-followup-modal");
    const formAddFollowup = document.getElementById("form-add-followup");

    let allFollowups = [];

    if (btnAddFollowupModal) {
        btnAddFollowupModal.addEventListener("click", () => modalFollowup.classList.add("active"));
    }
    if (btnCloseFollowupModal) {
        btnCloseFollowupModal.addEventListener("click", () => {
            modalFollowup.classList.remove("active");
            formAddFollowup.reset();
        });
    }
    if (btnCancelFollowupModal) {
        btnCancelFollowupModal.addEventListener("click", () => {
            modalFollowup.classList.remove("active");
            formAddFollowup.reset();
        });
    }

    async function loadFollowups() {
        try {
            const res = await fetch("/api/followups");
            if (res.ok) {
                allFollowups = await res.json();
                renderFollowups();
            }
        } catch (error) {
            console.error("Erro ao carregar follow-ups:", error);
        }
    }

    function renderFollowups() {
        if (!followupRulesContainer) return;
        followupRulesContainer.innerHTML = "";

        if (allFollowups.length === 0) {
            followupRulesContainer.innerHTML = `
                <div style="padding: 30px; text-align: center; color: rgba(255,255,255,0.4); border: 1px dashed rgba(255,255,255,0.1); border-radius: 8px;">
                    <i class="fa-regular fa-bell-slash" style="font-size: 24px; margin-bottom: 8px; display: block;"></i>
                    Nenhuma regra de follow-up cadastrada.
                </div>
            `;
            return;
        }

        allFollowups.forEach(rule => {
            const card = document.createElement("div");
            card.className = "follow-up-card";
            card.innerHTML = `
                <div class="rule-header">
                    <div class="rule-title">
                        <span class="service-tag">${rule.service}</span>
                        <h4>${rule.name}</h4>
                    </div>
                    <div class="rule-controls">
                        <button class="btn-delete-rule" title="Excluir Regra">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                        <label class="switch">
                            <input type="checkbox" class="followup-toggle-checkbox" ${rule.is_active ? 'checked' : ''}>
                            <span class="slider round"></span>
                        </label>
                    </div>
                </div>
                <p class="rule-description">Envia lembrete de pós-tratamento no WhatsApp do paciente <strong>${rule.delay_days} dia(s)</strong> após a realização.</p>
                <div class="rule-footer">
                    <span><i class="fa-regular fa-message"></i> Template: "${rule.message_template}"</span>
                </div>
            `;

            // Click no Switch Toggle
            const checkbox = card.querySelector(".followup-toggle-checkbox");
            checkbox.addEventListener("change", async () => {
                const isChecked = checkbox.checked;
                try {
                    const res = await fetch(`/api/followups/${rule.id}/toggle`, {
                        method: "PUT"
                    });
                    if (res.ok) {
                        rule.is_active = isChecked;
                    } else {
                        checkbox.checked = !isChecked;
                        alert("Falha ao alternar status da automação.");
                    }
                } catch (error) {
                    console.error("Erro toggle followup:", error);
                    checkbox.checked = !isChecked;
                    alert("Erro de conexão com o servidor.");
                }
            });

            // Click na lixeira (Deletar)
            const btnDelete = card.querySelector(".btn-delete-rule");
            btnDelete.addEventListener("click", async () => {
                if (confirm(`Deseja realmente excluir a automação "${rule.name}"?`)) {
                    try {
                        const res = await fetch(`/api/followups/${rule.id}`, {
                            method: "DELETE"
                        });
                        if (res.ok) {
                            allFollowups = allFollowups.filter(f => f.id !== rule.id);
                            renderFollowups();
                        } else {
                            alert("Falha ao excluir a automação.");
                        }
                    } catch (error) {
                        console.error("Erro ao deletar followup:", error);
                        alert("Erro de conexão.");
                    }
                }
            });

            followupRulesContainer.appendChild(card);
        });
    }

    if (formAddFollowup) {
        formAddFollowup.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("followup-name").value.trim();
            const service = document.getElementById("followup-service").value;
            const delay_days = parseInt(document.getElementById("followup-delay").value);
            const message_template = document.getElementById("followup-template").value.trim();

            const payload = { name, service, delay_days, message_template, is_active: true };

            try {
                const res = await fetch("/api/followups", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const newRule = await res.json();
                    allFollowups.push(newRule);
                    renderFollowups();
                    formAddFollowup.reset();
                    modalFollowup.classList.remove("active");
                } else {
                    alert("Erro ao criar nova automação de follow-up.");
                }
            } catch (error) {
                console.error("Erro ao cadastrar followup:", error);
                alert("Erro de conexão com o servidor.");
            }
        });
    }

    // Popula dinamicamente os seletores de serviço com os exames vindos do backend
    function populateServiceSelects() {
        const clientServiceSelect = document.getElementById("client-service");
        const followupServiceSelect = document.getElementById("followup-service");

        if (!filterServiceSelect || !clientServiceSelect || !followupServiceSelect) return;

        const filterVal = filterServiceSelect.value;
        const clientVal = clientServiceSelect.value;
        const followupVal = followupServiceSelect.value;

        // Limpa opções, mantendo apenas a padrão
        filterServiceSelect.innerHTML = `<option value="">Todos os Serviços</option>`;
        clientServiceSelect.innerHTML = `<option value="">Selecione o serviço...</option>`;
        followupServiceSelect.innerHTML = `<option value="">Selecione o serviço...</option>`;

        // Ordena exames alfabeticamente
        const sortedExams = [...allExams].sort((a, b) => a.name.localeCompare(b.name));

        sortedExams.forEach(exam => {
            // Filtro
            const optFilter = document.createElement("option");
            optFilter.value = exam.name;
            optFilter.textContent = exam.name;
            filterServiceSelect.appendChild(optFilter);

            // Cadastro Cliente
            const optClient = document.createElement("option");
            optClient.value = exam.name;
            optClient.textContent = `${exam.name} (a partir de R$ ${exam.price.toFixed(2).replace('.', ',')})`;
            clientServiceSelect.appendChild(optClient);

            // Follow-Up
            const optFollowup = document.createElement("option");
            optFollowup.value = exam.name;
            optFollowup.textContent = exam.name;
            followupServiceSelect.appendChild(optFollowup);
        });

        // Restaura valores selecionados previamente
        if (allExams.some(e => e.name === filterVal)) filterServiceSelect.value = filterVal;
        if (allExams.some(e => e.name === clientVal)) clientServiceSelect.value = clientVal;
        if (allExams.some(e => e.name === followupVal)) followupServiceSelect.value = followupVal;
    }

    // Monitora e avisa novos pedidos de atendimento humano (Toasts)
    function checkHumanHandoffNotifications() {
        allClients.forEach(client => {
            if (client.needs_human) {
                if (!activeHumanRequests.has(client.id)) {
                    activeHumanRequests.add(client.id);
                    showHumanNotificationToast(client);
                }
            } else {
                activeHumanRequests.delete(client.id);
            }
        });
    }

    // Exibe notificação toast flutuante no canto da tela
    function showHumanNotificationToast(client) {
        const toastContainer = document.getElementById("toast-container");
        if (!toastContainer) return;

        const toast = document.createElement("div");
        toast.className = "toast-notification";
        toast.setAttribute("data-client-id", client.id);

        const canal = client.source === "whatsapp" ? "WhatsApp" : "Instagram";
        const iconeCanal = client.source === "whatsapp" ? "fa-brands fa-whatsapp" : "fa-brands fa-instagram";

        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fa-solid fa-headset"></i>
            </div>
            <div class="toast-content">
                <h4>Suporte Humano Solicitado</h4>
                <p><strong>${client.name}</strong> solicita atendimento humano via ${canal}.</p>
            </div>
            <button class="toast-close-btn" title="Fechar">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;

        // Clique no corpo do toast
        toast.addEventListener("click", async (e) => {
            if (e.target.closest(".toast-close-btn")) return; // Deixa o botão de fechar tratar o evento dele

            // Abre link wa.me
            window.open(`https://wa.me/${client.phone}`, "_blank");

            // Resolve atendimento humano no backend
            try {
                const res = await fetch(`/api/clients/${client.id}/resolve-human`, {
                    method: "PUT"
                });
                if (res.ok) {
                    client.needs_human = false;
                    activeHumanRequests.delete(client.id);
                    renderClients();
                }
            } catch (err) {
                console.error("Erro ao resolver atendimento humano pelo toast:", err);
            }

            // Remove da tela
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 400);
        });

        // Clique para fechar notificação
        const closeBtn = toast.querySelector(".toast-close-btn");
        closeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 400);
        });

        toastContainer.appendChild(toast);

        // Animação de entrada
        setTimeout(() => toast.classList.add("show"), 100);

        // Auto dispensar depois de 15 segundos
        setTimeout(() => {
            if (toast.parentNode) {
                toast.classList.remove("show");
                setTimeout(() => {
                    if (toast.parentNode) toast.remove();
                }, 400);
            }
        }, 15000);
    }

    // 7.5. GERENCIAMENTO DE EXAMES (TABELA DE EXAMES & VALORES)
    const examSearchInput = document.getElementById("exam-search");
    const examsTableBody = document.getElementById("exams-table-body");
    const modalExam = document.getElementById("modal-exam");
    const btnAddExamModal = document.getElementById("btn-add-exam-modal");
    const btnCloseExamModal = document.getElementById("btn-close-exam-modal");
    const btnCancelExamModal = document.getElementById("btn-cancel-exam-modal");
    const formAddExam = document.getElementById("form-add-exam");
    const examIdInput = document.getElementById("exam-id");
    const examNameInput = document.getElementById("exam-name");
    const examPriceInput = document.getElementById("exam-price");
    const examCategorySelect = document.getElementById("exam-category");
    const btnSubmitExam = document.getElementById("btn-submit-exam");
    const examModalTitle = document.getElementById("exam-modal-title");

    if (btnAddExamModal) {
        btnAddExamModal.addEventListener("click", () => {
            examModalTitle.innerText = "Adicionar Procedimento";
            btnSubmitExam.innerText = "Cadastrar Procedimento";
            formAddExam.reset();
            examIdInput.value = "";
            modalExam.classList.add("active");
        });
    }

    if (btnCloseExamModal) {
        btnCloseExamModal.addEventListener("click", () => {
            modalExam.classList.remove("active");
            formAddExam.reset();
        });
    }

    if (btnCancelExamModal) {
        btnCancelExamModal.addEventListener("click", () => {
            modalExam.classList.remove("active");
            formAddExam.reset();
        });
    }

    if (examSearchInput) {
        examSearchInput.addEventListener("input", renderExams);
    }

    function renderExams() {
        if (!examsTableBody) return;
        examsTableBody.innerHTML = "";

        const query = examSearchInput ? examSearchInput.value.toLowerCase().trim() : "";

        const filtered = allExams.filter(exam => {
            return exam.name.toLowerCase().includes(query) || 
                   exam.category.toLowerCase().includes(query);
        });

        if (filtered.length === 0) {
            examsTableBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 30px; color: rgba(255,255,255,0.4);">
                        <i class="fa-regular fa-folder-open" style="font-size: 24px; margin-bottom: 8px; display: block;"></i>
                        Nenhum exame ou procedimento encontrado.
                    </td>
                </tr>
            `;
            return;
        }

        // Ordena por categoria e depois por nome
        filtered.sort((a, b) => {
            const catCompare = a.category.localeCompare(b.category);
            if (catCompare !== 0) return catCompare;
            return a.name.localeCompare(b.name);
        });

        filtered.forEach(exam => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${exam.name}</strong></td>
                <td><span class="badge-category ${getCategoryClass(exam.category)}"><i class="fa-solid fa-tag"></i> ${exam.category}</span></td>
                <td>R$ ${exam.price.toFixed(2).replace('.', ',')}</td>
                <td>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-secondary-outline btn-xs btn-edit-exam" data-id="${exam.id}" title="Editar">
                            <i class="fa-solid fa-pencil"></i>
                        </button>
                        <button class="btn btn-danger-outline btn-xs btn-delete-exam" data-id="${exam.id}" style="color: #ef4444; border-color: rgba(239, 68, 68, 0.2);" title="Excluir">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;

            // Clique no botão Editar
            tr.querySelector(".btn-edit-exam").addEventListener("click", () => {
                examModalTitle.innerText = "Editar Procedimento";
                btnSubmitExam.innerText = "Salvar Alterações";
                examIdInput.value = exam.id;
                examNameInput.value = exam.name;
                examPriceInput.value = exam.price;
                examCategorySelect.value = exam.category;
                modalExam.classList.add("active");
            });

            // Clique no botão Excluir
            tr.querySelector(".btn-delete-exam").addEventListener("click", async () => {
                if (confirm(`Deseja realmente excluir o procedimento "${exam.name}"?`)) {
                    try {
                        const res = await fetch(`/api/exams/${exam.id}`, {
                            method: "DELETE"
                        });
                        if (res.ok) {
                            allExams = allExams.filter(e => e.id !== exam.id);
                            renderExams();
                            populateServiceSelects();
                        } else {
                            alert("Falha ao excluir o procedimento.");
                        }
                    } catch (error) {
                        console.error("Erro ao deletar exame:", error);
                        alert("Erro de conexão com o servidor.");
                    }
                }
            });

            examsTableBody.appendChild(tr);
        });
    }

    if (formAddExam) {
        formAddExam.addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = examIdInput.value;
            const name = examNameInput.value.trim();
            const price = parseFloat(examPriceInput.value);
            const category = examCategorySelect.value;

            const payload = { name, price, category };

            const isEdit = id !== "";
            const url = isEdit ? `/api/exams/${id}` : "/api/exams";
            const method = isEdit ? "PUT" : "POST";

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const savedExam = await res.json();
                    if (isEdit) {
                        allExams = allExams.map(e => e.id === savedExam.id ? savedExam : e);
                    } else {
                        allExams.push(savedExam);
                    }
                    renderExams();
                    populateServiceSelects();
                    modalExam.classList.remove("active");
                    formAddExam.reset();
                } else {
                    alert(`Erro ao ${isEdit ? 'atualizar' : 'cadastrar'} o procedimento.`);
                }
            } catch (error) {
                console.error("Erro ao salvar exame:", error);
                alert("Erro de conexão com o servidor.");
            }
        });
    }

    // 7.7. GERENCIAMENTO DE SLOTS (AGENDA)
    if (btnAddSlotModal) {
        btnAddSlotModal.addEventListener("click", () => {
            formAddSlot.reset();
            modalSlot.classList.add("active");
        });
    }

    if (btnCloseSlotModal) {
        btnCloseSlotModal.addEventListener("click", () => {
            modalSlot.classList.remove("active");
            formAddSlot.reset();
        });
    }

    if (btnCancelSlotModal) {
        btnCancelSlotModal.addEventListener("click", () => {
            modalSlot.classList.remove("active");
            formAddSlot.reset();
        });
    }

    if (slotSearchInput) {
        slotSearchInput.addEventListener("input", renderSlots);
    }

    const WEEKDAYS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"];

    function renderSlots() {
        if (!slotsTableBody) return;
        slotsTableBody.innerHTML = "";

        const query = slotSearchInput ? slotSearchInput.value.toLowerCase().trim() : "";

        const filtered = allSlots.filter(slot => {
            const dayName = WEEKDAYS[slot.weekday] || "";
            return dayName.toLowerCase().includes(query) || 
                   slot.time_str.includes(query);
        });

        if (filtered.length === 0) {
            slotsTableBody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; padding: 30px; color: rgba(255,255,255,0.4);">
                        <i class="fa-regular fa-calendar-times" style="font-size: 24px; margin-bottom: 8px; display: block;"></i>
                        Nenhum horário configurado na grade.
                    </td>
                </tr>
            `;
            return;
        }

        filtered.forEach(slot => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${WEEKDAYS[slot.weekday]}</strong></td>
                <td>${slot.time_str}</td>
                <td>${slot.max_patients} paciente(s)</td>
                <td>
                    <span class="badge" style="background-color: ${slot.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)'}; color: ${slot.is_active ? '#10b981' : '#ef4444'};">
                        ${slot.is_active ? 'Ativo' : 'Inativo'}
                    </span>
                </td>
                <td>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-secondary-outline btn-xs btn-toggle-slot" data-id="${slot.id}" title="${slot.is_active ? 'Desativar' : 'Ativar'}">
                            <i class="fa-solid ${slot.is_active ? 'fa-eye-slash' : 'fa-eye'}"></i>
                        </button>
                        <button class="btn btn-danger-outline btn-xs btn-delete-slot" data-id="${slot.id}" style="color: #ef4444; border-color: rgba(239, 68, 68, 0.2);" title="Excluir">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;

            // Toggle active status
            tr.querySelector(".btn-toggle-slot").addEventListener("click", async () => {
                try {
                    const res = await fetch(`/api/slots/${slot.id}/toggle`, {
                        method: "PUT"
                    });
                    if (res.ok) {
                        const updated = await res.json();
                        allSlots = allSlots.map(s => s.id === updated.id ? updated : s);
                        renderSlots();
                    } else {
                        alert("Falha ao alternar status do horário.");
                    }
                } catch (error) {
                    console.error("Erro ao toggle slot:", error);
                    alert("Erro de conexão.");
                }
            });

            // Delete slot
            tr.querySelector(".btn-delete-slot").addEventListener("click", async () => {
                if (confirm(`Deseja realmente excluir este horário (${WEEKDAYS[slot.weekday]} às ${slot.time_str})?`)) {
                    try {
                        const res = await fetch(`/api/slots/${slot.id}`, {
                            method: "DELETE"
                        });
                        if (res.ok) {
                            allSlots = allSlots.filter(s => s.id !== slot.id);
                            renderSlots();
                        } else {
                            alert("Falha ao excluir o horário.");
                        }
                    } catch (error) {
                        console.error("Erro ao deletar slot:", error);
                        alert("Erro de conexão.");
                    }
                }
            });

            slotsTableBody.appendChild(tr);
        });
    }

    if (formAddSlot) {
        formAddSlot.addEventListener("submit", async (e) => {
            e.preventDefault();
            const weekday = parseInt(document.getElementById("slot-weekday").value);
            const time_str = document.getElementById("slot-time").value.trim();
            const max_patients = parseInt(document.getElementById("slot-max-patients").value);

            const payload = { weekday, time_str, max_patients, is_active: true };

            try {
                const res = await fetch("/api/slots", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const newSlot = await res.json();
                    allSlots.push(newSlot);
                    renderSlots();
                    modalSlot.classList.remove("active");
                    formAddSlot.reset();
                } else {
                    const err = await res.json();
                    alert("Erro ao cadastrar horário: " + (err.detail || "Erro desconhecido"));
                }
            } catch (error) {
                console.error("Erro ao salvar slot:", error);
                alert("Erro de conexão com o servidor.");
            }
        });
    }

    // 8. CARREGAMENTO DOS DADOS (E POPULADOR AUTOMÁTICO SE BANCO VAZIO)
    async function loadData() {
        try {
            const [clientsRes, adminsRes, examsRes, slotsRes] = await Promise.all([
                fetch("/api/clients"),
                fetch("/api/admins"),
                fetch("/api/exams"),
                fetch("/api/slots")
            ]);

            if (clientsRes.ok && adminsRes.ok && examsRes.ok && slotsRes.ok) {
                allClients = await clientsRes.json();
                allAdmins = await adminsRes.json();
                allExams = await examsRes.json();
                allSlots = await slotsRes.json();

                // Se o banco estiver vazio, populate com dados realistas da Clínica Lúmina automaticamente!
                if (allClients.length === 0 && allAdmins.length === 0) {
                    console.log("Banco de dados vazio detectado. Populando banco local com dados reais...");
                    await populateInitialDatabase();
                    return; // populateInitialDatabase fará o recarregamento
                }

                // Popula os dropdowns dinamicamente
                populateServiceSelects();

                renderClients();
                renderAdmins();

                // Renderiza tabela se estiver na aba de exames ou agenda
                const activeNav = document.querySelector(".nav-item.active");
                if (activeNav) {
                    const tab = activeNav.getAttribute("data-tab");
                    if (tab === "exams") {
                        renderExams();
                    } else if (tab === "schedule") {
                        renderSlots();
                    }
                }

                // Verifica suporte humano em tempo real
                checkHumanHandoffNotifications();

                await loadFollowups(); // Carrega follow-ups de forma assíncrona
            }
        } catch (error) {
            console.error("Erro ao carregar dados da API:", error);
            console.log("Servidor inacessível. Usando dados fallback locais...");
        }
    }

    async function populateInitialDatabase() {
        const mockClients = [
            { name: "Ana Maria Silva", cpf: "123.456.789-10", phone: "5511999999999", service: "Limpeza", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Ana", appointment_date: "25/05/2026 às 14:00", upsell_success: true, upsell_service: "Clareamento", status: "confirmed" },
            { name: "Carlos Eduardo Costa", cpf: "987.654.321-00", phone: "5511988888888", service: "Implante", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Carlos", appointment_date: "28/05/2026 às 10:30", upsell_success: false, upsell_service: null, status: "confirmed" },
            { name: "Mariana Souza", cpf: "456.789.123-45", phone: "5511977777777", service: "Clareamento", source: "instagram", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Mariana", appointment_date: "01/06/2026 às 16:00", upsell_success: true, upsell_service: "Profilaxia", status: "confirmed" },
            { name: "Guilherme Santos", cpf: "321.654.987-12", phone: "5511966666666", service: "Aparelho", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Guilherme", appointment_date: null, upsell_success: false, upsell_service: null, status: "pending" },
            { name: "Beatriz Ramos", cpf: "654.123.987-00", phone: "5511955555555", service: "Canal", source: "instagram", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz", appointment_date: null, upsell_success: false, upsell_service: null, status: "pending" }
        ];

        const mockAdmins = [
            { name: "Dr. Felipe Costa", email: "felipe.costa@clinicalumina.com.br", role: "Dentista / Clínico Geral", avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=Felipe" },
            { name: "Dra. Carolina Mello", email: "carolina.mello@clinicalumina.com.br", role: "Ortodontista", avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=Carolina" },
            { name: "Larissa Vasconcelos", email: "larissa.v@clinicalumina.com.br", role: "Atendente de Recepção", avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=Larissa" }
        ];

        // Cadastra cada admin via POST API
        for (const admin of mockAdmins) {
            await fetch("/api/admins", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(admin)
            });
        }

        // Cadastra cada cliente via POST API
        for (const client of mockClients) {
            await fetch("/api/clients", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(client)
            });
        }

        // Recarrega agora que está populado
        loadData();
    }

    // Inicialização
    loadData();

    // Polling a cada 5 segundos para atualizar dados e checar atendimento humano
    setInterval(loadData, 5000);
});

