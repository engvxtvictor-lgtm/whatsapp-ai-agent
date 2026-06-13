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

            const cleanPhone = client.phone.split(':')[0].replace(/\D/g, '');

            card.innerHTML = `
                <div class="client-card-header" style="width: 100%; display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input type="checkbox" class="client-card-select" ${isSelected ? 'checked' : ''} style="position: static; opacity: 0.6; width: 18px; height: 18px; cursor: pointer; margin: 0;">
                        ${statusBadgeHtml}
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn-edit-client" title="Editar Paciente" style="position: static; opacity: 1; pointer-events: all; background: rgba(197, 168, 128, 0.1); color: var(--gold-dark); border: none; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 15px;"><i class="fa-solid fa-pen"></i></button>
                        <button class="btn-delete-client" title="Excluir Paciente" style="position: static; opacity: 1; pointer-events: all; background: rgba(255, 59, 48, 0.1); color: var(--status-red); border: none; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 15px;"><i class="fa-solid fa-trash-can"></i></button>
                    </div>
                </div>
                
                <h4 class="client-name" style="margin-top: 0;">${client.name}</h4>
                <p class="client-meta" style="display: flex; align-items: center; gap: 8px;">
                    <strong>CPF:</strong> ${client.cpf || 'Não informado'}
                    ${client.cpf ? `<button class="btn-icon-copy-inline" title="Copiar CPF" onclick="copyToClipboard('${client.cpf}')" style="background: none; border: none; color: var(--text-muted); cursor: pointer;"><i class="fa-regular fa-copy"></i></button>` : ''}
                </p>
                <p class="client-meta" style="display: flex; align-items: center; gap: 8px;">
                    <strong>Tel:</strong> 
                    <a href="https://wa.me/${cleanPhone}" target="_blank" class="whatsapp-link" style="color: var(--whatsapp-green); text-decoration: none; font-weight: 500;">
                        <i class="fa-brands fa-whatsapp"></i> ${client.phone.split(':')[0]}
                    </a>
                    <button class="btn-icon-copy-inline" title="Copiar Telefone" onclick="copyToClipboard('${cleanPhone}')" style="background: none; border: none; color: var(--text-muted); cursor: pointer;"><i class="fa-regular fa-copy"></i></button>
                </p>
                
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

            // Clique na lixeira (Deletar Paciente)
            const btnDeleteClient = card.querySelector(".btn-delete-client");
            btnDeleteClient.addEventListener("click", async (e) => {
                e.stopPropagation(); // Evita abrir wa.me ou alternar seleção do card
                if (confirm(`Deseja realmente excluir o paciente "${client.name}"?`)) {
                    btnDeleteClient.disabled = true;
                    btnDeleteClient.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
                    try {
                        const response = await fetch(`${API_BASE}/api/clients/${client.id}`, {
                            method: "DELETE"
                        });
                        if (response.ok) {
                            allClients = allClients.filter(c => c.id !== client.id);
                            selectedClients.delete(client.id);
                            
                            // Remover qualquer notificação toast ativa desse cliente
                            const activeToast = document.querySelector(`.toast-notification[data-client-id="${client.id}"]`);
                            if (activeToast) {
                                activeToast.classList.remove("show");
                                setTimeout(() => activeToast.remove(), 400);
                            }
                            
                            renderClients();
                        } else {
                            alert("Falha ao excluir o paciente.");
                            btnDeleteClient.disabled = false;
                            btnDeleteClient.innerHTML = `<i class="fa-solid fa-trash-can"></i>`;
                        }
                    } catch (error) {
                        console.error("Erro ao deletar cliente:", error);
                        alert("Erro de conexão com o servidor.");
                        btnDeleteClient.disabled = false;
                        btnDeleteClient.innerHTML = `<i class="fa-solid fa-trash-can"></i>`;
                    }
                }
            });

            // Clique no botão editar
            const btnEditClient = card.querySelector(".btn-edit-client");
            if (btnEditClient) {
                btnEditClient.addEventListener("click", (e) => {
                    e.stopPropagation();
                    openEditClientModal(client);
                });
            }

            // Clique no toggle da IA
            const iaCheckbox = card.querySelector(".ia-toggle-checkbox");
            iaCheckbox.addEventListener("click", async (e) => {
                e.stopPropagation(); // Evita selecionar o card
                const checked = iaCheckbox.checked;
                try {
                    const response = await fetch(`${API_BASE}/api/sessions/${client.phone}/toggle-ai`, {
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
                    const adminEmail = localStorage.getItem("admin_email");
                    const currentAdmin = allAdmins.find(a => a.email === adminEmail);
                    const loggedAdminName = currentAdmin ? currentAdmin.name : "Dra. Ana Souza";
                    btnConfirm.disabled = true;
                    btnConfirm.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Aceitando...`;

                    try {
                        const response = await fetch(`${API_BASE}/api/clients/${client.id}/confirm`, {
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
                        const response = await fetch(`${API_BASE}/api/clients/${client.id}/cancel`, {
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
                    // Prevent opening wa.me for @lid since WhatsApp doesn't support it
                    if (client.phone.includes("@lid")) {
                        alert("Atenção: Este cliente está usando um número oculto (Meta LID). O WhatsApp Web não permite abrir conversas com IDs ocultos via link. Por favor, responda a este cliente diretamente pelo aplicativo oficial do WhatsApp (onde a conversa já está iniciada).");
                    } else {
                        // Open wa.me link directly (clean phone number first to remove device suffix like :1)
                        const cleanPhone = client.phone.split(':')[0].replace(/[^0-9]/g, '');
                        window.open(`https://wa.me/${cleanPhone}`, "_blank");
                    }
                    
                    // Resolve needs_human on the backend
                    try {
                        const res = await fetch(`${API_BASE}/api/clients/${client.id}/resolve-human`, {
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
    
    // ============================================
    // Lógica do Modal de Edição de Paciente
    // ============================================
    const modalEditClient = document.getElementById("modal-edit-client");
    const btnCloseEditClient = document.getElementById("btn-close-edit-client-modal");
    const btnCancelEditClient = document.getElementById("btn-cancel-edit-client");
    const formEditClient = document.getElementById("form-edit-client");
    
    window.copyToClipboard = function(text) {
        if (!text) return;
        
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                showToast("Copiado!", "success");
            }).catch(err => {
                console.error('Falha ao copiar: ', err);
                fallbackCopyTextToClipboard(text);
            });
        } else {
            fallbackCopyTextToClipboard(text);
        }
    };

    function fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        
        // Evitar scroll
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                showToast("Copiado!", "success");
            } else {
                showToast("Erro ao copiar. Tente manualmente.", "error");
            }
        } catch (err) {
            console.error('Falha no fallback de cópia', err);
            showToast("Erro ao copiar. Tente manualmente.", "error");
        }
        
        document.body.removeChild(textArea);
    }

    window.openEditClientModal = function(client) {
        document.getElementById("edit-client-id").value = client.id;
        document.getElementById("edit-client-name").value = client.name || "";
        document.getElementById("edit-client-cpf").value = client.cpf || "";
        document.getElementById("edit-client-phone").value = client.phone || "";
        document.getElementById("edit-client-service").value = client.service || "";
        document.getElementById("edit-client-date").value = client.appointment_date || "";
        
        modalEditClient.classList.add("active");
    };

    function closeEditClientModal() {
        modalEditClient.classList.remove("active");
        formEditClient.reset();
    }

    if(btnCloseEditClient) btnCloseEditClient.addEventListener("click", closeEditClientModal);
    if(btnCancelEditClient) btnCancelEditClient.addEventListener("click", closeEditClientModal);
    
    if(formEditClient) {
        formEditClient.addEventListener("submit", async (e) => {
            e.preventDefault();
            const btnSave = document.getElementById("btn-save-edit-client");
            const originalText = btnSave.innerHTML;
            btnSave.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
            btnSave.disabled = true;
            
            const clientId = document.getElementById("edit-client-id").value;
            // Procurar cliente original
            const originalClient = allClients.find(c => c.id == clientId);
            
            const updatedData = {
                name: document.getElementById("edit-client-name").value,
                cpf: document.getElementById("edit-client-cpf").value,
                phone: document.getElementById("edit-client-phone").value,
                service: document.getElementById("edit-client-service").value,
                appointment_date: document.getElementById("edit-client-date").value,
                
                // Mantenha os outros dados originais
                source: originalClient.source,
                status: originalClient.status,
                upsell_success: originalClient.upsell_success,
                upsell_service: originalClient.upsell_service,
                ai_active: originalClient.ai_active,
                exam_id: originalClient.exam_id
            };
            
            try {
                const token = localStorage.getItem("token");
                const response = await fetch(`${API_BASE}/api/clients/${clientId}`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify(updatedData)
                });
                
                if (response.ok) {
                    const savedClient = await response.json();
                    // Atualiza localmente
                    const index = allClients.findIndex(c => c.id == clientId);
                    if (index !== -1) {
                        allClients[index] = savedClient;
                    }
                    showToast("Paciente atualizado com sucesso!", "success");
                    closeEditClientModal();
                    renderClients();
                } else {
                    showToast("Erro ao atualizar paciente.", "error");
                }
            } catch (error) {
                console.error("Erro na edição:", error);
                showToast("Erro de comunicação com servidor.", "error");
            } finally {
                btnSave.innerHTML = originalText;
                btnSave.disabled = false;
            }
        });
    }