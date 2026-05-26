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

    function showToast(title, message, type = "success") {
        const toastContainer = document.getElementById("toast-container");
        if (!toastContainer) {
            alert(`${title}: ${message}`);
            return;
        }

        const toast = document.createElement("div");
        toast.className = "toast-notification show";
        
        let iconClass = "fa-solid fa-circle-check";
        let color = "#10b981"; // green for success
        if (type === "error") {
            iconClass = "fa-solid fa-triangle-exclamation";
            color = "#ef4444"; // red for error
        } else if (type === "warning") {
            iconClass = "fa-solid fa-circle-exclamation";
            color = "#f59e0b"; // yellow/orange for warning
        }

        toast.style.borderLeftColor = color;

        toast.innerHTML = `
            <div class="toast-icon" style="color: ${color};">
                <i class="${iconClass}"></i>
            </div>
            <div class="toast-content">
                <h4 style="color: ${color};">${title}</h4>
                <p>${message}</p>
            </div>
            <button class="toast-close-btn" title="Fechar">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;

        toastContainer.appendChild(toast);

        // Slide in animation handled by adding class, but force layout redraw
        toast.offsetHeight; 
        toast.style.transform = "translateX(0)";

        // Auto dismiss after 4 seconds
        const dismissTimeout = setTimeout(() => {
            toast.style.transform = "translateX(120%)";
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 400);
        }, 4000);

        // Close button click
        toast.querySelector(".toast-close-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            clearTimeout(dismissTimeout);
            toast.style.transform = "translateX(120%)";
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 400);
        });
    }

    function isValidSlotTime(timeStr) {
        const parts = timeStr.split(':');
        if (parts.length !== 2) return false;
        const hour = parseInt(parts[0], 10);
        const minute = parseInt(parts[1], 10);
        if (isNaN(hour) || isNaN(minute)) return false;
        
        const minutes = hour * 60 + minute;
        const minM = 8 * 60;   // 08:00
        const maxM = 12 * 60;  // 12:00
        const minT = 14 * 60;  // 14:00
        const maxT = 18 * 60;  // 18:00
        
        return (minutes >= minM && minutes <= maxM) || (minutes >= minT && minutes <= maxT);
    }
    function openAddSlotModal(weekday, timeStr) {
        if (formAddSlot) formAddSlot.reset();
        
        const selectWeekday = document.getElementById("slot-weekday");
        const inputTime = document.getElementById("slot-time");
        
        if (selectWeekday) selectWeekday.value = weekday.toString();
        if (inputTime) inputTime.value = timeStr;
        
        if (modalSlot) modalSlot.classList.add("active");
    }

    function isValidSlotTime(timeStr) {
        const parts = timeStr.split(':');
        if (parts.length !== 2) return false;
        const hour = parseInt(parts[0], 10);
        const minute = parseInt(parts[1], 10);
        if (isNaN(hour) || isNaN(minute)) return false;
        
        const minutes = hour * 60 + minute;
        const minM = 8 * 60;   // 08:00
        const maxM = 12 * 60;  // 12:00
        const minT = 14 * 60;  // 14:00
        const maxT = 18 * 60;  // 18:00
        
        return (minutes >= minM && minutes <= maxM) || (minutes >= minT && minutes <= maxT);
    }

    function renderSlots() {
        if (!scheduleGridContainer) return;
        scheduleGridContainer.innerHTML = "";

        const query = slotSearchInput ? slotSearchInput.value.toLowerCase().trim() : "";

        // Filtrar slots conforme query de busca
        const filtered = allSlots.filter(slot => {
            const dayName = WEEKDAYS[slot.weekday] || "";
            return dayName.toLowerCase().includes(query) || 
                   slot.time_str.includes(query);
        });

        // Se nenhum slot for encontrado E há uma busca ativa
        if (filtered.length === 0 && query !== "") {
            scheduleGridContainer.innerHTML = `
                <div class="schedule-empty-state" style="grid-column: 1 / -1; text-align: center; padding: 40px; color: rgba(42, 49, 60, 0.45); background: var(--bg-card); border-radius: 12px; border: 1px dashed var(--border-gold-soft);">
                    <i class="fa-regular fa-calendar-xmark" style="font-size: 32px; color: var(--gold-primary); margin-bottom: 12px; display: block;"></i>
                    Nenhum horário correspondente à busca.
                </div>
            `;
            return;
        }

        // 1. Obter lista de horas (incluindo slots fora do padrão)
        const STANDARD_HOURS = ["08:00", "09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"];
        const hoursSet = new Set(STANDARD_HOURS);
        allSlots.forEach(slot => {
            if (slot.time_str && slot.time_str.includes(':')) {
                const parts = slot.time_str.split(':');
                const hr = parts[0].padStart(2, '0') + ":00";
                hoursSet.add(hr);
            }
        });
        const sortedHours = Array.from(hoursSet).sort();

        // 2. Criar a estrutura do grid do calendário
        const calendarGrid = document.createElement("div");
        calendarGrid.className = "calendar-grid";

        // Cabeçalhos (Hora + Dias da semana)
        let headerHtml = `<div class="calendar-header-cell time-column-header">Hora</div>`;
        WEEKDAYS.forEach(day => {
            headerHtml += `<div class="calendar-header-cell">${day.split('-')[0]}</div>`; // Seg, Ter, etc.
        });
        calendarGrid.innerHTML = headerHtml;

        // Renderizar linhas de horários
        sortedHours.forEach(hourStr => {
            // Se for após o meio-dia, e a hora anterior foi 12:00, renderiza o divisor de almoço
            if (hourStr === "14:00") {
                calendarGrid.innerHTML += `
                    <div class="calendar-time-cell separator-row-time">12h - 14h</div>
                    <div class="calendar-cell separator-row-cells" style="grid-column: span 7;">
                        <i class="fa-solid fa-mug-hot" style="margin-right: 6px;"></i> Intervalo de Almoço
                    </div>
                `;
            }

            // Célula do Horário
            calendarGrid.innerHTML += `<div class="calendar-time-cell">${hourStr}</div>`;

            // Células de cada dia da semana para essa hora
            for (let d = 0; d < 7; d++) {
                const cellSlots = filtered.filter(slot => {
                    if (slot.weekday !== d) return false;
                    const parts = slot.time_str.split(':');
                    const hr = parts[0].padStart(2, '0') + ":00";
                    return hr === hourStr;
                });

                let cellContent = "";
                if (cellSlots.length > 0) {
                    cellContent = cellSlots.map(slot => {
                        let statusClass = "status-free";
                        let clientsHtml = "";

                        if (slot.clients && slot.clients.length > 0) {
                            statusClass = "status-booked";
                            clientsHtml = slot.clients.map(c => {
                                let statusColor = '#c5a880'; // pendente (gold/brown)
                                let statusText = 'Pendente';
                                if (c.status === 'confirmed') {
                                    statusColor = '#10b981';
                                    statusText = 'Confirmado';
                                } else if (c.status === 'cancelled') {
                                    statusColor = '#ef4444';
                                    statusText = 'Cancelado';
                                }
                                return `
                                    <div class="slot-patient-row">
                                        <span class="slot-patient-name" title="${c.name}">${c.name}</span>
                                        <span class="badge slot-patient-badge" style="background-color: ${statusColor}1A; color: ${statusColor}; border: 1px solid ${statusColor}33;">
                                            ${statusText}
                                        </span>
                                    </div>
                                `;
                            }).join('');
                        } else {
                            clientsHtml = `
                                <div class="slot-available-row">
                                    <i class="fa-regular fa-circle-check"></i> Disponível
                                </div>
                            `;
                        }

                        const activeClass = slot.is_active ? "active" : "inactive";

                        return `
                            <div class="calendar-slot-card ${activeClass} ${statusClass}">
                                <div class="slot-card-header">
                                    <span class="slot-time"><i class="fa-regular fa-clock" style="margin-right: 3px;"></i>${slot.time_str}</span>
                                    <span class="badge slot-status-badge ${slot.is_active ? 'badge-active' : 'badge-inactive'}">
                                        ${slot.is_active ? 'Ativo' : 'Inativo'}
                                    </span>
                                </div>
                                <div class="slot-card-body">
                                    ${clientsHtml}
                                </div>
                                <div class="slot-card-actions">
                                    <button class="btn-slot-action btn-toggle-slot" data-id="${slot.id}" title="${slot.is_active ? 'Desativar' : 'Ativar'}">
                                        <i class="fa-solid ${slot.is_active ? 'fa-eye-slash' : 'fa-eye'}"></i>
                                    </button>
                                    <button class="btn-slot-action btn-delete-slot" data-id="${slot.id}" title="Excluir">
                                        <i class="fa-solid fa-trash-can"></i>
                                    </button>
                                </div>
                            </div>
                        `;
                    }).join('');
                } else {
                    // Sem slots configurados: Célula vazia clicável para adicionar novo horário
                    cellContent = `
                        <div class="calendar-empty-cell" data-weekday="${d}" data-time="${hourStr}" title="Clique para adicionar horário às ${hourStr} na ${WEEKDAYS[d]}">
                            <i class="fa-solid fa-plus"></i>
                        </div>
                    `;
                }

                calendarGrid.innerHTML += `<div class="calendar-cell">${cellContent}</div>`;
            }
        });

        scheduleGridContainer.appendChild(calendarGrid);

        // Bind de Evento para Célula Vazia (Clique para adicionar)
        scheduleGridContainer.querySelectorAll(".calendar-empty-cell").forEach(cell => {
            cell.addEventListener("click", (e) => {
                e.preventDefault();
                const weekday = cell.getAttribute("data-weekday");
                const time = cell.getAttribute("data-time");
                openAddSlotModal(weekday, time);
            });
        });

        // Bind de Eventos dos botões de Toggle
        scheduleGridContainer.querySelectorAll(".btn-toggle-slot").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                e.stopPropagation();
                const slotId = parseInt(btn.getAttribute("data-id"));
                try {
                    const res = await fetch(`${API_BASE}/api/slots/${slotId}/toggle`, {
                        method: "PUT"
                    });
                    if (res.ok) {
                        const updated = await res.json();
                        allSlots = allSlots.map(s => s.id === updated.id ? updated : s);
                        renderSlots();
                        showToast("Sucesso", "Status do horário atualizado com sucesso!", "success");
                    } else {
                        showToast("Erro", "Falha ao alternar status do horário.", "error");
                    }
                } catch (error) {
                    console.error("Erro ao toggle slot:", error);
                    showToast("Erro", "Erro de conexão.", "error");
                }
            });
        });

        // Bind de Eventos dos botões de Excluir
        scheduleGridContainer.querySelectorAll(".btn-delete-slot").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                e.stopPropagation();
                const slotId = parseInt(btn.getAttribute("data-id"));
                const slot = allSlots.find(s => s.id === slotId);
                if (!slot) return;

                if (confirm(`Deseja realmente excluir este horário (${WEEKDAYS[slot.weekday]} às ${slot.time_str})?`)) {
                    try {
                        const res = await fetch(`${API_BASE}/api/slots/${slotId}`, {
                            method: "DELETE"
                        });
                        if (res.ok) {
                            allSlots = allSlots.filter(s => s.id !== slotId);
                            renderSlots();
                            showToast("Sucesso", "Horário excluído com sucesso!", "success");
                        } else {
                            showToast("Erro", "Falha ao excluir o horário.", "error");
                        }
                    } catch (error) {
                        console.error("Erro ao deletar slot:", error);
                        showToast("Erro", "Erro de conexão.", "error");
                    }
                }
            });
        });
    }

    if (formAddSlot) {
        formAddSlot.addEventListener("submit", async (e) => {
            e.preventDefault();
            const weekday = parseInt(document.getElementById("slot-weekday").value);
            const time_str = document.getElementById("slot-time").value.trim();
            const max_patients = parseInt(document.getElementById("slot-max-patients").value);

            // Validar o horário do slot
            if (!isValidSlotTime(time_str)) {
                showToast("Horário Inválido", "A agenda da clínica atende apenas de 08:00 às 12:00 e de 14:00 às 18:00.", "warning");
                return;
            }

            const payload = { weekday, time_str, max_patients, is_active: true };

            try {
                const res = await fetch(`${API_BASE}/api/slots`, {
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
                    showToast("Sucesso", "Horário cadastrado com sucesso!", "success");
                } else {
                    const err = await res.json();
                    showToast("Erro ao cadastrar", err.detail || "Erro desconhecido", "error");
                }
            } catch (error) {
                console.error("Erro ao salvar slot:", error);
                showToast("Erro de Conexão", "Erro ao conectar com o servidor.", "error");
            }
        });
    }