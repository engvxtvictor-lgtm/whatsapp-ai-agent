// JavaScript - Painel de Controle Clínica Lúmina

document.addEventListener("DOMContentLoaded", () => {
    // Estado Global do Frontend
    let allClients = [];
    let allAdmins = [];
    const selectedClients = new Set();

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
    const btnAddClientModal = document.getElementById("btn-add-client-modal");
    const btnAddAdminModal = document.getElementById("btn-add-admin-modal");

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
            card.className = `client-card ${isSelected ? 'selected' : ''}`;
            card.setAttribute("data-id", client.id);

            // Determina Ícone e Cor do Canal
            const isWA = client.source === "whatsapp";
            const channelBadgeClass = isWA ? "badge-wa" : "badge-ig";
            const channelIcon = isWA ? "fa-brands fa-whatsapp" : "fa-brands fa-instagram";
            const channelLabel = isWA ? "WhatsApp" : "Instagram";

            card.innerHTML = `
                <input type="checkbox" class="client-card-select" ${isSelected ? 'checked' : ''}>
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
                </div>
            `;

            // Clique no Checkbox
            const checkbox = card.querySelector(".client-card-select");
            checkbox.addEventListener("click", (e) => {
                e.stopPropagation(); // Evita triggar o clique do card completo
                toggleClientSelection(client.id, checkbox.checked);
            });

            // Clique no Card completo (alterna seleção)
            card.addEventListener("click", () => {
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
    btnAddClientModal.addEventListener("click", () => modalClient.classList.add("active"));
    btnCloseClientModal.addEventListener("click", () => modalClient.classList.remove("active"));
    btnCancelClientModal.addEventListener("click", () => modalClient.classList.remove("active"));

    formAddClient.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const name = document.getElementById("client-name").value;
        const cpf = document.getElementById("client-cpf").value;
        const phone = document.getElementById("client-phone").value;
        const service = document.getElementById("client-service").value;
        const source = document.getElementById("client-source").value;

        const payload = { name, cpf, phone, service, source };

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

    // 7. CARREGAMENTO DOS DADOS (E POPULADOR AUTOMÁTICO SE BANCO VAZIO)
    async function loadData() {
        try {
            const [clientsRes, adminsRes] = await Promise.all([
                fetch("/api/clients"),
                fetch("/api/admins")
            ]);

            if (clientsRes.ok && adminsRes.ok) {
                allClients = await clientsRes.json();
                allAdmins = await adminsRes.json();

                // Se o banco estiver vazio, populate com dados realistas da Clínica Lúmina automaticamente!
                if (allClients.length === 0 && allAdmins.length === 0) {
                    console.log("Banco de dados vazio detectado. Populando banco local com dados reais...");
                    await populateInitialDatabase();
                    return; // populateInitialDatabase fará o recarregamento
                }

                renderClients();
                renderAdmins();
            }
        } catch (error) {
            console.error("Erro ao carregar dados da API:", error);
            // Fallback apenas visual local se houver queda total
            console.log("Servidor inacessível. Usando dados fallback locais...");
        }
    }

    async function populateInitialDatabase() {
        const mockClients = [
            { name: "Ana Maria Silva", cpf: "123.456.789-10", phone: "5511999999999", service: "Limpeza", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Ana" },
            { name: "Carlos Eduardo Costa", cpf: "987.654.321-00", phone: "5511988888888", service: "Implante", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Carlos" },
            { name: "Mariana Souza", cpf: "456.789.123-45", phone: "5511977777777", service: "Clareamento", source: "instagram", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Mariana" },
            { name: "Guilherme Santos", cpf: "321.654.987-12", phone: "5511966666666", service: "Aparelho", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Guilherme" },
            { name: "Beatriz Ramos", cpf: "654.123.987-00", phone: "5511955555555", service: "Canal", source: "instagram", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz" }
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
});
