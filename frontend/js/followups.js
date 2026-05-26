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