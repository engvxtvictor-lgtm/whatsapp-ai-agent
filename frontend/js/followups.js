// 7. GERENCIAMENTO DE AUTOMACÕES DE FOLLOW-UP
    const followupRulesContainer = document.getElementById("follow-up-rules-container");

    let allFollowups = [];

    // Toggle de Sub-Painéis (Disparar na Hora vs Nova Automação)
    const togglePills = document.querySelectorAll(".toggle-pill");
    const subPanelInstant = document.getElementById("sub-panel-instant");
    const subPanelAutomation = document.getElementById("sub-panel-automation");

    if (togglePills) {
        togglePills.forEach(pill => {
            pill.addEventListener("click", () => {
                togglePills.forEach(p => p.classList.remove("active"));
                pill.classList.add("active");

                const panel = pill.getAttribute("data-panel");
                if (panel === "instant") {
                    if (subPanelInstant) subPanelInstant.style.display = "block";
                    if (subPanelAutomation) subPanelAutomation.style.display = "none";
                } else if (panel === "automation") {
                    if (subPanelInstant) subPanelInstant.style.display = "none";
                    if (subPanelAutomation) subPanelAutomation.style.display = "block";
                }
            });
        });
    }

    async function loadFollowups() {
        try {
            const res = await fetch(`${API_BASE}/api/followups`);
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
                <div style="padding: 30px; text-align: center; color: var(--charcoal-text); opacity: 0.6; border: 1px dashed rgba(197, 168, 128, 0.3); border-radius: 8px; background-color: rgba(197, 168, 128, 0.03);">
                    <i class="fa-regular fa-bell-slash" style="font-size: 24px; margin-bottom: 8px; display: block; color: var(--gold-primary);"></i>
                    Nenhuma regra de follow-up cadastrada.
                </div>
            `;
            return;
        }

        allFollowups.forEach(rule => {
            // Pacientes afetados / elegíveis
            let clientsListHtml = "";
            if (rule.affected_clients && rule.affected_clients.length > 0) {
                const clientsListItems = rule.affected_clients.map(c => {
                    const isSent = c.sent_status === "Enviado";
                    const statusBadgeColor = isSent ? "#10b981" : "#c5a880";
                    const statusBg = isSent ? "rgba(16, 185, 129, 0.1)" : "rgba(197, 168, 128, 0.1)";
                    const dateText = isSent ? `em ${c.sent_at}` : `Consulta: ${c.appointment_date || 'Sem data'}`;
                    
                    return `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(197,168,128,0.1); font-size: 13px;">
                            <span style="font-weight: 500; color: var(--charcoal-text);"><i class="fa-regular fa-user" style="margin-right: 6px; color: var(--gold-primary);"></i>${c.name}</span>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 11px; color: var(--charcoal-text); opacity: 0.6;">${dateText}</span>
                                <span class="badge" style="font-size: 10px; padding: 2px 6px; background-color: ${statusBg}; color: ${statusBadgeColor}; border: 1px solid ${statusBadgeColor}33;">
                                    ${c.sent_status}
                                </span>
                            </div>
                        </div>
                    `;
                }).join('');

                clientsListHtml = `
                    <div class="affected-clients-panel" style="margin-top: 15px; padding: 12px; background: rgba(197, 168, 128, 0.05); border: 1px solid rgba(197, 168, 128, 0.15); border-radius: 8px;">
                        <h5 style="margin: 0 0 10px 0; color: var(--gold-primary); font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                            <i class="fa-solid fa-users"></i> Pacientes Afetados (${rule.affected_clients.length})
                        </h5>
                        <div style="max-height: 120px; overflow-y: auto; padding-right: 4px;">
                            ${clientsListItems}
                        </div>
                    </div>
                `;
            } else {
                clientsListHtml = `
                    <div class="affected-clients-panel" style="margin-top: 15px; padding: 12px; background: rgba(0, 0, 0, 0.01); border: 1px dashed rgba(197, 168, 128, 0.15); border-radius: 8px; text-align: center;">
                        <p style="margin: 0; color: var(--charcoal-text); opacity: 0.5; font-size: 12px; font-style: italic;">
                            <i class="fa-solid fa-user-slash" style="margin-right: 5px;"></i>Nenhum paciente confirmado elegível para esta regra.
                        </p>
                    </div>
                `;
            }

            const ruleDescription = rule.is_recurring 
                ? `Envia lembrete de pós-tratamento no WhatsApp <strong>${rule.delay_days} dia(s)</strong> após a realização, <span class="badge" style="font-size: 11px; padding: 2px 6px; background-color: rgba(197, 168, 128, 0.15); color: var(--gold-dark); font-weight: 600;"><i class="fa-solid fa-arrows-spin"></i> Repetindo a cada ${rule.recurrence_interval} dias</span>`
                : `Envia lembrete de pós-tratamento no WhatsApp <strong>${rule.delay_days} dia(s)</strong> após a realização (Disparo Único).`;

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
                <p class="rule-description">${ruleDescription}</p>
                
                ${clientsListHtml}
                
                <div class="rule-footer" style="margin-top: 15px;">
                    <span><i class="fa-regular fa-message"></i> Template: "${rule.message_template}"</span>
                </div>
            `;

            // Click no Switch Toggle
            const checkbox = card.querySelector(".followup-toggle-checkbox");
            checkbox.addEventListener("change", async () => {
                const isChecked = checkbox.checked;
                try {
                    const res = await fetch(`${API_BASE}/api/followups/${rule.id}/toggle`, {
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
                        const res = await fetch(`${API_BASE}/api/followups/${rule.id}`, {
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

    // Toggle de exibição do campo de recorrência na criação inline
    const inlineFollowupIsRecurringSelect = document.getElementById("inline-followup-is-recurring");
    const groupInlineRecurrence = document.getElementById("group-inline-recurrence");
    if (inlineFollowupIsRecurringSelect && groupInlineRecurrence) {
        inlineFollowupIsRecurringSelect.addEventListener("change", () => {
            if (inlineFollowupIsRecurringSelect.value === "true") {
                groupInlineRecurrence.style.display = "block";
                const recurrenceIntervalInput = document.getElementById("inline-followup-recurrence-interval");
                if (recurrenceIntervalInput) recurrenceIntervalInput.required = true;
            } else {
                groupInlineRecurrence.style.display = "none";
                const recurrenceIntervalInput = document.getElementById("inline-followup-recurrence-interval");
                if (recurrenceIntervalInput) recurrenceIntervalInput.required = false;
            }
        });
    }

    const formInlineFollowup = document.getElementById("form-inline-followup");
    if (formInlineFollowup) {
        formInlineFollowup.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("inline-followup-name").value.trim();
            const service = document.getElementById("inline-followup-service").value;
            const delay_days = parseInt(document.getElementById("inline-followup-delay").value);
            const message_template = document.getElementById("inline-followup-template").value.trim();
            const is_recurring = document.getElementById("inline-followup-is-recurring").value === "true";
            const recurrence_interval = is_recurring ? parseInt(document.getElementById("inline-followup-recurrence-interval").value) : 0;

            const payload = { 
                name, 
                service, 
                delay_days, 
                message_template, 
                is_active: true, 
                is_recurring, 
                recurrence_interval 
            };

            try {
                const res = await fetch(`${API_BASE}/api/followups`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const newRule = await res.json();
                    allFollowups.push(newRule);
                    renderFollowups();
                    formInlineFollowup.reset();
                    if (groupInlineRecurrence) groupInlineRecurrence.style.display = "none";
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
        const followupServiceSelect = document.getElementById("inline-followup-service");

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
                const res = await fetch(`${API_BASE}/api/clients/${client.id}/resolve-human`, {
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