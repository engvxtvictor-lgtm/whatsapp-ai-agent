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

    let visibleScheduleMonth = new Date();
    visibleScheduleMonth.setDate(1);

    function getMonthLabel(date) {
        return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    }

    function getISODate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function getAppointmentText(client) {
        if (client.slot_date) {
            const parts = client.slot_date.split("-");
            if (parts.length === 3) {
                return `${parts[2]}/${parts[1]}/${parts[0]}${client.slot_time ? " às " + client.slot_time : ""}`;
            }
        }
        return client.appointment_date || "Sem horário";
    }

    function renderSlots() {
        if (!scheduleGridContainer) return;

        const query = slotSearchInput ? slotSearchInput.value.toLowerCase().trim() : "";
        const monthStart = new Date(visibleScheduleMonth.getFullYear(), visibleScheduleMonth.getMonth(), 1);
        const monthEnd = new Date(visibleScheduleMonth.getFullYear(), visibleScheduleMonth.getMonth() + 1, 0);
        const gridStart = new Date(monthStart);
        gridStart.setDate(monthStart.getDate() - monthStart.getDay());
        const todayISO = getISODate(new Date());

        const appointmentsByDate = {};
        allClients.forEach(client => {
            if (!client.slot_date) return;
            const haystack = `${client.name || ""} ${client.service || ""} ${client.slot_time || ""} ${client.status || ""}`.toLowerCase();
            if (query && !haystack.includes(query)) return;
            if (!appointmentsByDate[client.slot_date]) appointmentsByDate[client.slot_date] = [];
            appointmentsByDate[client.slot_date].push(client);
        });

        scheduleGridContainer.innerHTML = `
            <div class="month-calendar-shell">
                <div class="month-calendar-toolbar">
                    <button class="btn-calendar-nav" id="btn-schedule-prev" title="Mês anterior"><i class="fa-solid fa-chevron-left"></i></button>
                    <div>
                        <h4>${getMonthLabel(visibleScheduleMonth)}</h4>
                        <span>${monthStart.toLocaleDateString("pt-BR")} a ${monthEnd.toLocaleDateString("pt-BR")}</span>
                    </div>
                    <button class="btn-calendar-nav" id="btn-schedule-next" title="Próximo mês"><i class="fa-solid fa-chevron-right"></i></button>
                    <button class="btn-calendar-today" id="btn-schedule-today">Hoje</button>
                </div>
                <div class="month-calendar-weekdays">
                    <span>Dom</span><span>Seg</span><span>Ter</span><span>Qua</span><span>Qui</span><span>Sex</span><span>Sáb</span>
                </div>
                <div class="month-calendar-grid" id="month-calendar-grid"></div>
            </div>
        `;

        const grid = document.getElementById("month-calendar-grid");
        for (let index = 0; index < 42; index++) {
            const day = new Date(gridStart);
            day.setDate(gridStart.getDate() + index);
            const iso = getISODate(day);
            const isCurrentMonth = day.getMonth() === visibleScheduleMonth.getMonth();
            const weekday = (day.getDay() + 6) % 7;
            const weekdaySlots = allSlots.filter(slot => slot.weekday === weekday && slot.is_active);
            const appointments = (appointmentsByDate[iso] || []).sort((a, b) => (a.slot_time || "").localeCompare(b.slot_time || ""));

            const appointmentsHtml = appointments.length
                ? appointments.map(client => {
                    const statusClass = `status-${client.status || "pending"}`;
                    const statusLabel = client.status === "confirmed" ? "Confirmado" : client.status === "cancelled" ? "Cancelado" : "Pendente";
                    return `
                        <div class="month-appointment ${statusClass}" title="${client.name} - ${getAppointmentText(client)}">
                            <strong>${client.slot_time || "--:--"}</strong>
                            <span>${client.name}</span>
                            <small>${client.service}</small>
                            <em>${statusLabel}</em>
                        </div>
                    `;
                }).join("")
                : `<div class="month-empty-day">Sem agendamentos</div>`;

            grid.innerHTML += `
                <div class="month-day-cell ${isCurrentMonth ? "" : "muted"} ${iso === todayISO ? "today" : ""}">
                    <div class="month-day-header">
                        <span>${day.getDate()}</span>
                        <button class="month-add-slot" data-weekday="${weekday}" title="Adicionar horário neste dia da semana">
                            <i class="fa-solid fa-plus"></i>
                        </button>
                    </div>
                    <div class="month-day-meta">
                        ${weekdaySlots.length ? `${weekdaySlots.length} horário(s) ativo(s)` : "Sem grade ativa"}
                    </div>
                    <div class="month-day-appointments">${appointmentsHtml}</div>
                </div>
            `;
        }

        document.getElementById("btn-schedule-prev").addEventListener("click", () => {
            visibleScheduleMonth.setMonth(visibleScheduleMonth.getMonth() - 1);
            renderSlots();
        });
        document.getElementById("btn-schedule-next").addEventListener("click", () => {
            visibleScheduleMonth.setMonth(visibleScheduleMonth.getMonth() + 1);
            renderSlots();
        });
        document.getElementById("btn-schedule-today").addEventListener("click", () => {
            visibleScheduleMonth = new Date();
            visibleScheduleMonth.setDate(1);
            renderSlots();
        });
        scheduleGridContainer.querySelectorAll(".month-add-slot").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                openAddSlotModal(btn.getAttribute("data-weekday"), "09:00");
            });
        });
    }

    let visibleScheduleWeek = getStartOfWeek(new Date());
    const GCAL_START_HOUR = 7;
    const GCAL_END_HOUR = 19;
    const GCAL_HOUR_HEIGHT = 64;

    function getStartOfWeek(date) {
        const start = new Date(date);
        start.setHours(0, 0, 0, 0);
        start.setDate(start.getDate() - start.getDay());
        return start;
    }

    function addDays(date, days) {
        const next = new Date(date);
        next.setDate(next.getDate() + days);
        return next;
    }

    function getWeekRangeLabel(startDate) {
        const endDate = addDays(startDate, 6);
        const sameMonth = startDate.getMonth() === endDate.getMonth();
        if (sameMonth) {
            return `${startDate.toLocaleDateString("pt-BR", { month: "long" })} de ${startDate.getFullYear()}`;
        }
        return `${startDate.toLocaleDateString("pt-BR", { month: "short" })} - ${endDate.toLocaleDateString("pt-BR", { month: "short", year: "numeric" })}`;
    }

    function getGcalTimeLabel(hour) {
        if (hour === 0) return "12 AM";
        if (hour < 12) return `${hour} AM`;
        if (hour === 12) return "12 PM";
        return `${hour - 12} PM`;
    }

    function getClientTime(client) {
        if (client.slot_time) return client.slot_time;
        const match = (client.appointment_date || "").match(/\b(\d{1,2})(?::|h)(\d{2})?\b/);
        if (!match) return null;
        const hour = String(parseInt(match[1], 10)).padStart(2, "0");
        const minute = match[2] || "00";
        return `${hour}:${minute}`;
    }

    function renderSlots() {
        if (!scheduleGridContainer) return;

        const query = slotSearchInput ? slotSearchInput.value.toLowerCase().trim() : "";
        const weekDays = Array.from({ length: 7 }, (_, index) => addDays(visibleScheduleWeek, index));
        const todayISO = getISODate(new Date());
        const gridHeight = (GCAL_END_HOUR - GCAL_START_HOUR) * GCAL_HOUR_HEIGHT;
        const hourRows = Array.from({ length: GCAL_END_HOUR - GCAL_START_HOUR + 1 }, (_, index) => GCAL_START_HOUR + index);
        const hourGuides = hourRows.slice(0, -1).map((hour, index) => `
            <div class="gcal-hour-guide" style="top: ${index * GCAL_HOUR_HEIGHT}px;">
                <span>${getGcalTimeLabel(hour)}</span>
            </div>
        `).join("");

        const dayHeaders = weekDays.map(day => {
            const iso = getISODate(day);
            return `
                <div class="gcal-day-header ${iso === todayISO ? "today" : ""}">
                    <span>${day.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "").toUpperCase()}</span>
                    <strong>${day.getDate()}</strong>
                </div>
            `;
        }).join("");

        const dayColumns = weekDays.map(day => {
            const iso = getISODate(day);
            const dayIndex = (day.getDay() + 6) % 7;
            const activeSlots = allSlots.filter(slot => slot.weekday === dayIndex && slot.is_active);
            const appointments = allClients
                .filter(client => client.slot_date === iso)
                .filter(client => {
                    if (!query) return true;
                    return `${client.name || ""} ${client.service || ""} ${client.slot_time || ""} ${client.status || ""}`.toLowerCase().includes(query);
                })
                .sort((a, b) => (getClientTime(a) || "").localeCompare(getClientTime(b) || ""));

            const events = appointments.map(client => {
                const time = getClientTime(client);
                if (!time) return "";
                const [hour, minute] = time.split(":").map(Number);
                const top = Math.max(0, ((hour - GCAL_START_HOUR) * GCAL_HOUR_HEIGHT) + (minute / 60 * GCAL_HOUR_HEIGHT));
                const statusLabel = client.status === "confirmed" ? "Confirmado" : client.status === "cancelled" ? "Cancelado" : "Pendente";
                return `
                    <div class="gcal-event status-${client.status || "pending"}" style="top: ${top + 4}px; min-height: 46px;" title="${client.name} - ${getAppointmentText(client)}">
                        <strong>${client.name}</strong>
                        <span>${time} - ${client.service}</span>
                        <em>${statusLabel}</em>
                    </div>
                `;
            }).join("");

            return `
                <div class="gcal-day-column ${iso === todayISO ? "today" : ""}" style="height: ${gridHeight}px;" data-weekday="${dayIndex}">
                    <div class="gcal-slot-note">${activeSlots.length ? `${activeSlots.length} horário(s)` : ""}</div>
                    ${events}
                </div>
            `;
        }).join("");

        scheduleGridContainer.innerHTML = `
            <div class="gcal-shell">
                <div class="gcal-toolbar">
                    <button class="gcal-today-btn" id="btn-schedule-today">Hoje</button>
                    <button class="gcal-nav-btn" id="btn-schedule-prev" title="Semana anterior"><i class="fa-solid fa-chevron-left"></i></button>
                    <button class="gcal-nav-btn" id="btn-schedule-next" title="Próxima semana"><i class="fa-solid fa-chevron-right"></i></button>
                    <h4>${getWeekRangeLabel(visibleScheduleWeek)}</h4>
                    <button class="gcal-view-btn" type="button">Semana <i class="fa-solid fa-caret-down"></i></button>
                </div>
                <div class="gcal-board">
                    <div class="gcal-timezone">GMT-03</div>
                    <div class="gcal-week-header">${dayHeaders}</div>
                    <div class="gcal-time-grid" style="height: ${gridHeight}px;">${hourGuides}</div>
                    <div class="gcal-days-grid" style="height: ${gridHeight}px;">${dayColumns}</div>
                </div>
            </div>
        `;

        document.getElementById("btn-schedule-prev").addEventListener("click", () => {
            visibleScheduleWeek = addDays(visibleScheduleWeek, -7);
            renderSlots();
        });
        document.getElementById("btn-schedule-next").addEventListener("click", () => {
            visibleScheduleWeek = addDays(visibleScheduleWeek, 7);
            renderSlots();
        });
        document.getElementById("btn-schedule-today").addEventListener("click", () => {
            visibleScheduleWeek = getStartOfWeek(new Date());
            renderSlots();
        });
    }

    let gcalVisibleDate = new Date(2026, 5, 14);
    let gcalViewMode = "week";
    let gcalViewMenuOpen = false;
    let gcalShowWeekends = true;
    let gcalShowCancelled = true;
    let gcalShowCompleted = true;
    const gcalFilters = {
        pending: true,
        confirmed: true,
        cancelled: true,
        human: true
    };
    const GCAL2_START_HOUR = 7;
    const GCAL2_END_HOUR = 19;
    const GCAL2_HOUR_HEIGHT = 64;
    let gcalComposer = null;
    let gcalCustomEvents = [];

    try {
        gcalCustomEvents = JSON.parse(localStorage.getItem("lumina_gcal_events") || "[]");
    } catch {
        gcalCustomEvents = [];
    }

    function gcalSaveCustomEvents() {
        localStorage.setItem("lumina_gcal_events", JSON.stringify(gcalCustomEvents));
    }

    function gcalEscape(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function gcalClone(date) {
        const cloned = new Date(date);
        cloned.setHours(0, 0, 0, 0);
        return cloned;
    }

    function gcalStartOfWeek(date) {
        const start = gcalClone(date);
        start.setDate(start.getDate() - start.getDay());
        return start;
    }

    function gcalAddDays(date, days) {
        const next = gcalClone(date);
        next.setDate(next.getDate() + days);
        return next;
    }

    function gcalMonthLabel(date) {
        return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    }

    function gcalViewLabel() {
        const labels = {
            day: "Dia",
            week: "Semana",
            month: "Mês",
            year: "Ano",
            schedule: "Programação",
            "4days": "4 dias"
        };
        return labels[gcalViewMode] || "Semana";
    }

    function gcalPeriodLabel() {
        if (gcalViewMode === "year") return String(gcalVisibleDate.getFullYear());
        if (gcalViewMode === "month") return gcalMonthLabel(gcalVisibleDate);
        if (gcalViewMode === "day") {
            return gcalVisibleDate.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
        }
        if (gcalViewMode === "schedule") return "Programação";
        const start = gcalViewMode === "4days" ? gcalClone(gcalVisibleDate) : gcalStartOfWeek(gcalVisibleDate);
        const end = gcalAddDays(start, gcalViewMode === "4days" ? 3 : 6);
        if (start.getMonth() === end.getMonth()) return gcalMonthLabel(start);
        return `${start.toLocaleDateString("pt-BR", { month: "short" })} - ${end.toLocaleDateString("pt-BR", { month: "short", year: "numeric" })}`;
    }

    function gcalVisibleDays() {
        if (gcalViewMode === "day") return [gcalClone(gcalVisibleDate)];
        const total = gcalViewMode === "4days" ? 4 : 7;
        const start = gcalViewMode === "4days" ? gcalClone(gcalVisibleDate) : gcalStartOfWeek(gcalVisibleDate);
        return Array.from({ length: total }, (_, index) => gcalAddDays(start, index))
            .filter(day => gcalShowWeekends || (day.getDay() !== 0 && day.getDay() !== 6));
    }

    function gcalShiftPeriod(amount) {
        if (gcalViewMode === "day") gcalVisibleDate = gcalAddDays(gcalVisibleDate, amount);
        else if (gcalViewMode === "4days") gcalVisibleDate = gcalAddDays(gcalVisibleDate, amount * 4);
        else if (gcalViewMode === "month") gcalVisibleDate = new Date(gcalVisibleDate.getFullYear(), gcalVisibleDate.getMonth() + amount, 1);
        else if (gcalViewMode === "year") gcalVisibleDate = new Date(gcalVisibleDate.getFullYear() + amount, 0, 1);
        else gcalVisibleDate = gcalAddDays(gcalVisibleDate, amount * 7);
    }

    function gcalStatusLabel(status) {
        if (status === "confirmed") return "Confirmado";
        if (status === "cancelled") return "Cancelado";
        if (status === "needs_human") return "Atendimento";
        return "Pendente";
    }

    function gcalClientTime(client) {
        return getClientTime(client) || "09:00";
    }

    function gcalMatchesFilters(client, query) {
        const status = client.status || "pending";
        if (status === "cancelled" && (!gcalFilters.cancelled || !gcalShowCancelled)) return false;
        if (status === "confirmed" && (!gcalFilters.confirmed || !gcalShowCompleted)) return false;
        if (status === "needs_human" && !gcalFilters.human) return false;
        if ((status === "pending" || !status) && !gcalFilters.pending) return false;
        if (!query) return true;
        return `${client.name || ""} ${client.service || ""} ${client.slot_time || ""} ${client.status || ""}`.toLowerCase().includes(query);
    }

    function gcalFilteredAppointments(query = "") {
        const backendEvents = allClients
            .filter(client => client.slot_date)
            .map(client => ({ ...client, gcal_id: `client-${client.id || client.phone || client.slot_date}-${client.slot_time || ""}` }));
        const customEvents = gcalCustomEvents.map(event => ({
            id: event.id,
            gcal_id: event.id,
            name: event.title || "Sem título",
            service: event.description || event.calendar || "Evento",
            slot_date: event.date,
            slot_time: event.time,
            appointment_date: event.date,
            status: event.status || "confirmed",
            is_custom_event: true,
            location: event.location || "",
            guests: event.guests || ""
        }));

        return [...backendEvents, ...customEvents]
            .filter(client => client.slot_date)
            .filter(client => gcalMatchesFilters(client, query))
            .sort((a, b) => `${a.slot_date} ${gcalClientTime(a)}`.localeCompare(`${b.slot_date} ${gcalClientTime(b)}`));
    }

    function gcalMiniCalendar() {
        const monthStart = new Date(gcalVisibleDate.getFullYear(), gcalVisibleDate.getMonth(), 1);
        const gridStart = gcalAddDays(monthStart, -monthStart.getDay());
        const selectedISO = getISODate(gcalVisibleDate);
        const todayISO = getISODate(new Date());
        const days = Array.from({ length: 42 }, (_, index) => {
            const day = gcalAddDays(gridStart, index);
            const iso = getISODate(day);
            return `
                <button type="button" class="${day.getMonth() === monthStart.getMonth() ? "" : "muted"} ${iso === selectedISO ? "selected" : ""} ${iso === todayISO ? "today" : ""}" data-gcal-mini-date="${iso}">
                    ${day.getDate()}
                </button>
            `;
        }).join("");

        return `
            <div class="gcal-mini-calendar">
                <div class="gcal-mini-title">
                    <strong>${gcalMonthLabel(monthStart)}</strong>
                    <span>
                        <button type="button" data-gcal-mini-nav="-1"><i class="fa-solid fa-chevron-left"></i></button>
                        <button type="button" data-gcal-mini-nav="1"><i class="fa-solid fa-chevron-right"></i></button>
                    </span>
                </div>
                <div class="gcal-mini-weekdays"><span>D</span><span>S</span><span>T</span><span>Q</span><span>Q</span><span>S</span><span>S</span></div>
                <div class="gcal-mini-days">${days}</div>
            </div>
        `;
    }

    function gcalSidebar() {
        const filters = [
            ["pending", "#f9ab00", "Pendentes"],
            ["confirmed", "#0b8043", "Confirmados"],
            ["cancelled", "#d93025", "Cancelados"],
            ["human", "#8e24aa", "Atendimento humano"]
        ].map(([key, color, label]) => `
            <label class="gcal-calendar-filter">
                <input type="checkbox" data-gcal-filter="${key}" ${gcalFilters[key] ? "checked" : ""}>
                <span style="--calendar-color:${color}"></span>
                ${label}
            </label>
        `).join("");

        return `
            <aside class="gcal-sidebar">
                <button type="button" class="gcal-create-btn" id="gcal-create-slot"><i class="fa-solid fa-plus"></i> Criar <i class="fa-solid fa-caret-down"></i></button>
                ${gcalMiniCalendar()}
                <div class="gcal-sidebar-section">
                    <div class="gcal-section-title"><span>Agenda da clínica</span><i class="fa-solid fa-chevron-up"></i></div>
                    <label class="gcal-calendar-filter"><input type="checkbox" checked><span style="--calendar-color:#039be5"></span> Clínica Lúmina</label>
                </div>
                <div class="gcal-sidebar-section">
                    <div class="gcal-section-title"><span>Filtros da agenda</span><i class="fa-solid fa-chevron-up"></i></div>
                    ${filters}
                </div>
            </aside>
        `;
    }

    function gcalViewMenu() {
        if (!gcalViewMenuOpen) return "";
        const item = (mode, label, key) => `
            <button type="button" class="${gcalViewMode === mode ? "active" : ""}" data-gcal-view="${mode}">
                <span>${label}</span><kbd>${key}</kbd>
            </button>
        `;
        return `
            <div class="gcal-view-menu">
                ${item("day", "Dia", "D")}
                ${item("week", "Semana", "W")}
                ${item("month", "Mês", "M")}
                ${item("year", "Ano", "Y")}
                ${item("schedule", "Programação", "A")}
                ${item("4days", "4 dias", "X")}
                <hr>
                <label><input type="checkbox" id="gcal-toggle-weekends" ${gcalShowWeekends ? "checked" : ""}> Mostrar fins de semana</label>
                <label><input type="checkbox" id="gcal-toggle-cancelled" ${gcalShowCancelled ? "checked" : ""}> Mostrar eventos recusados</label>
                <label><input type="checkbox" id="gcal-toggle-completed" ${gcalShowCompleted ? "checked" : ""}> Mostrar tarefas concluídas</label>
            </div>
        `;
    }

    function gcalTimeLabel(hour) {
        if (hour < 12) return `${hour} AM`;
        if (hour === 12) return "12 PM";
        return `${hour - 12} PM`;
    }

    function gcalTimeGrid(query) {
        const days = gcalVisibleDays();
        const todayISO = getISODate(new Date());
        const gridHeight = (GCAL2_END_HOUR - GCAL2_START_HOUR) * GCAL2_HOUR_HEIGHT;
        const guides = Array.from({ length: GCAL2_END_HOUR - GCAL2_START_HOUR }, (_, index) => {
            const hour = GCAL2_START_HOUR + index;
            return `<div class="gcal-hour-guide" style="top:${index * GCAL2_HOUR_HEIGHT}px;"><span>${gcalTimeLabel(hour)}</span></div>`;
        }).join("");

        const headers = days.map(day => {
            const iso = getISODate(day);
            return `
                <div class="gcal-day-header ${iso === todayISO ? "today" : ""}">
                    <span>${day.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "").toUpperCase()}</span>
                    <strong>${day.getDate()}</strong>
                </div>
            `;
        }).join("");

        const appointments = gcalFilteredAppointments(query);
        const columns = days.map(day => {
            const iso = getISODate(day);
            const dayIndex = (day.getDay() + 6) % 7;
            const activeSlots = allSlots.filter(slot => slot.weekday === dayIndex && slot.is_active);
            const events = appointments.filter(client => client.slot_date === iso).map(client => {
                const time = gcalClientTime(client);
                const [hour, minute] = time.split(":").map(Number);
                const top = Math.max(0, ((hour - GCAL2_START_HOUR) * GCAL2_HOUR_HEIGHT) + ((minute || 0) / 60 * GCAL2_HOUR_HEIGHT));
                return `
                    <div class="gcal-event status-${client.status || "pending"}" data-gcal-event-id="${gcalEscape(client.gcal_id)}" style="top:${top + 4}px; min-height:46px;" title="${gcalEscape(client.name)} - ${gcalEscape(getAppointmentText(client))}">
                        <strong>${client.name || "Cliente"}</strong>
                        <span>${time} - ${client.service || "Servico"}</span>
                        <em>${gcalStatusLabel(client.status)}</em>
                    </div>
                `;
            }).join("");
            return `
                <div class="gcal-day-column ${iso === todayISO ? "today" : ""}" data-gcal-column-date="${iso}" style="height:${gridHeight}px;">
                    <button type="button" class="gcal-column-add" data-weekday="${dayIndex}" data-gcal-column-date="${iso}">+</button>
                    <div class="gcal-slot-note">${activeSlots.length ? `${activeSlots.length} horario(s)` : ""}</div>
                    ${events}
                </div>
            `;
        }).join("");

        return `
            <div class="gcal-board">
                <div class="gcal-timezone">GMT-03</div>
                <div class="gcal-week-header" style="grid-template-columns:repeat(${days.length}, minmax(0, 1fr));">${headers}</div>
                <div class="gcal-time-grid" style="height:${gridHeight}px;">${guides}</div>
                <div class="gcal-days-grid" style="height:${gridHeight}px; grid-template-columns:repeat(${days.length}, minmax(0, 1fr));">${columns}</div>
            </div>
        `;
    }

    function gcalMonthView(query) {
        const monthStart = new Date(gcalVisibleDate.getFullYear(), gcalVisibleDate.getMonth(), 1);
        const gridStart = gcalAddDays(monthStart, -monthStart.getDay());
        const todayISO = getISODate(new Date());
        const appointments = gcalFilteredAppointments(query);
        const cells = Array.from({ length: 42 }, (_, index) => {
            const day = gcalAddDays(gridStart, index);
            const iso = getISODate(day);
            const chips = appointments.filter(client => client.slot_date === iso).slice(0, 4).map(client => `
                <div class="gcal-month-chip status-${client.status || "pending"}" data-gcal-event-id="${gcalEscape(client.gcal_id)}">
                    <strong>${gcalClientTime(client)}</strong> ${client.name || "Cliente"}
                </div>
            `).join("");
            return `
                <button type="button" class="gcal-month-cell ${day.getMonth() === monthStart.getMonth() ? "" : "muted"} ${iso === todayISO ? "today" : ""}" data-gcal-date="${iso}">
                    <span>${day.getDate()}</span>
                    ${chips || "<small>Sem eventos</small>"}
                </button>
            `;
        }).join("");
        return `
            <div class="gcal-month-view">
                <div class="gcal-month-weekdays"><span>Dom</span><span>Seg</span><span>Ter</span><span>Qua</span><span>Qui</span><span>Sex</span><span>Sab</span></div>
                <div class="gcal-month-grid">${cells}</div>
            </div>
        `;
    }

    function gcalScheduleList(query) {
        const appointments = gcalFilteredAppointments(query);
        const items = appointments.length ? appointments.map(client => `
            <div class="gcal-schedule-item status-${client.status || "pending"}">
                <time>${getAppointmentText(client)}</time>
                <div><strong>${client.name || "Cliente"}</strong><span>${client.service || "Servico"} - ${gcalStatusLabel(client.status)}</span></div>
            </div>
        `).join("") : `<div class="gcal-empty-state">Nenhum agendamento encontrado.</div>`;
        return `<div class="gcal-schedule-list">${items}</div>`;
    }

    function gcalYearView(query) {
        const months = Array.from({ length: 12 }, (_, month) => {
            const ref = new Date(gcalVisibleDate.getFullYear(), month, 1);
            const monthAppointments = gcalFilteredAppointments(query).filter(client => {
                const [year, clientMonth] = (client.slot_date || "").split("-").map(Number);
                return year === ref.getFullYear() && clientMonth === month + 1;
            });
            return `
                <button type="button" class="gcal-year-month" data-gcal-month="${month}">
                    <strong>${ref.toLocaleDateString("pt-BR", { month: "long" })}</strong>
                    <span>${monthAppointments.length} evento(s)</span>
                </button>
            `;
        }).join("");
        return `<div class="gcal-year-view">${months}</div>`;
    }

    function gcalOpenComposer(dateISO = getISODate(gcalVisibleDate), time = "09:00", eventId = null) {
        const existing = eventId ? gcalFilteredAppointments("").find(event => event.gcal_id === eventId) : null;
        gcalComposer = {
            id: existing?.is_custom_event ? existing.gcal_id : null,
            sourceId: eventId,
            name: existing?.name || "",
            cpf: existing?.cpf || "",
            phone: existing?.phone || "",
            examId: existing?.exam_id || "",
            service: existing?.service || "",
            date: existing?.slot_date || dateISO,
            time: gcalClientTime(existing || { slot_time: time }),
            notes: existing?.notes || "",
            readOnly: !!existing && !existing.is_custom_event
        };
        gcalViewMenuOpen = false;
        renderSlots();
    }

    function gcalServiceOptions(selectedExamId = "", selectedService = "") {
        const selectedId = selectedExamId ? String(selectedExamId) : "";
        const hasSelectedInList = (allExams || []).some(exam => selectedId === String(exam.id) || (!selectedId && selectedService === exam.name));
        const options = (allExams || []).map(exam => {
            const value = String(exam.id);
            const selected = selectedId === value || (!selectedId && selectedService === exam.name) ? "selected" : "";
            return `<option value="${gcalEscape(value)}" data-service="${gcalEscape(exam.name)}" ${selected}>${gcalEscape(exam.name)}</option>`;
        }).join("");

        if (options) {
            const otherSelected = selectedService && !hasSelectedInList ? "selected" : "";
            return `<option value="">Selecione o procedimento...</option>${options}<option value="__other__" data-service="" ${otherSelected}>Outro procedimento</option>`;
        }

        const fallback = selectedService || "Consulta odontologica";
        return `<option value="">Selecione o procedimento...</option><option value="__other__" data-service="" selected>Outro procedimento</option>`;
    }

    function gcalComposerHtml() {
        if (!gcalComposer) return "";
        const date = gcalComposer.date || getISODate(gcalVisibleDate);
        const time = gcalComposer.time || "09:00";
        const name = gcalEscape(gcalComposer.name);
        const cpf = gcalEscape(gcalComposer.cpf);
        const phone = gcalEscape(gcalComposer.phone);
        const notes = gcalEscape(gcalComposer.notes);
        const service = gcalEscape(gcalComposer.service);
        const isReadOnly = gcalComposer.readOnly;
        const showCustomService = gcalComposer.service && !(allExams || []).some(exam => exam.name === gcalComposer.service || String(exam.id) === String(gcalComposer.examId));
        return `
            <div class="gcal-composer-backdrop">
                <form class="gcal-composer" id="gcal-composer-form">
                    <div class="gcal-composer-drag"><i class="fa-solid fa-grip-lines"></i><button type="button" id="gcal-composer-close"><i class="fa-solid fa-xmark"></i></button></div>
                    <div class="gcal-composer-heading">
                        <strong>${isReadOnly ? "Agendamento do paciente" : "Novo agendamento"}</strong>
                        <span>${isReadOnly ? "Dados registrados no painel" : "Preencha os dados para criar a solicitacao"}</span>
                    </div>
                    <label class="gcal-composer-row">
                        <i class="fa-regular fa-clock"></i>
                        <span>
                            <input type="date" id="gcal-composer-date" value="${date}" ${isReadOnly ? "disabled" : ""} required>
                            <input type="time" id="gcal-composer-time" value="${time}" ${isReadOnly ? "disabled" : ""} required>
                        </span>
                    </label>
                    <label class="gcal-composer-row">
                        <i class="fa-regular fa-user"></i>
                        <input id="gcal-composer-name" placeholder="Nome completo do paciente" value="${name}" ${isReadOnly ? "readonly" : ""} required>
                    </label>
                    <label class="gcal-composer-row">
                        <i class="fa-regular fa-id-card"></i>
                        <input id="gcal-composer-cpf" placeholder="CPF" value="${cpf}" ${isReadOnly ? "readonly" : ""} required>
                    </label>
                    <label class="gcal-composer-row">
                        <i class="fa-brands fa-whatsapp"></i>
                        <input id="gcal-composer-phone" placeholder="Telefone / WhatsApp" value="${phone}" ${isReadOnly ? "readonly" : ""} required>
                    </label>
                    <label class="gcal-composer-row">
                        <i class="fa-solid fa-tooth"></i>
                        <select id="gcal-composer-service" ${isReadOnly ? "disabled" : ""} required data-current-service="${service}">
                            ${gcalServiceOptions(gcalComposer.examId, gcalComposer.service)}
                        </select>
                    </label>
                    <label class="gcal-composer-row gcal-custom-service-row ${showCustomService ? "" : "is-hidden"}">
                        <i class="fa-solid fa-pen-to-square"></i>
                        <input id="gcal-composer-custom-service" placeholder="Digite o procedimento desejado" value="${showCustomService ? service : ""}" ${isReadOnly ? "readonly" : ""}>
                    </label>
                    <label class="gcal-composer-row">
                        <i class="fa-solid fa-align-left"></i>
                        <textarea id="gcal-composer-notes" placeholder="Observacao interna (opcional)" ${isReadOnly ? "readonly" : ""}>${notes}</textarea>
                    </label>
                    <div class="gcal-composer-actions">
                        ${isReadOnly ? "" : `<button type="submit" class="gcal-save-btn">Criar agendamento</button>`}
                    </div>
                </form>
            </div>
        `;
    }

    function gcalRenderView(query) {
        if (gcalViewMode === "month") return gcalMonthView(query);
        if (gcalViewMode === "year") return gcalYearView(query);
        if (gcalViewMode === "schedule") return gcalScheduleList(query);
        return gcalTimeGrid(query);
    }

    function gcalBindControls() {
        document.getElementById("gcal-prev")?.addEventListener("click", () => {
            gcalShiftPeriod(-1);
            gcalViewMenuOpen = false;
            renderSlots();
        });
        document.getElementById("gcal-next")?.addEventListener("click", () => {
            gcalShiftPeriod(1);
            gcalViewMenuOpen = false;
            renderSlots();
        });
        document.getElementById("gcal-today")?.addEventListener("click", () => {
            gcalVisibleDate = new Date();
            gcalViewMenuOpen = false;
            renderSlots();
        });
        document.getElementById("gcal-view-button")?.addEventListener("click", () => {
            gcalViewMenuOpen = !gcalViewMenuOpen;
            renderSlots();
        });
        scheduleGridContainer.querySelectorAll("[data-gcal-view]").forEach(btn => {
            btn.addEventListener("click", () => {
                gcalViewMode = btn.getAttribute("data-gcal-view");
                gcalViewMenuOpen = false;
                renderSlots();
            });
        });
        scheduleGridContainer.querySelectorAll("[data-gcal-mini-date]").forEach(btn => {
            btn.addEventListener("click", () => {
                const [year, month, day] = btn.getAttribute("data-gcal-mini-date").split("-").map(Number);
                gcalVisibleDate = new Date(year, month - 1, day);
                gcalViewMenuOpen = false;
                renderSlots();
            });
        });
        scheduleGridContainer.querySelectorAll(".gcal-month-cell").forEach(btn => {
            btn.addEventListener("click", (event) => {
                const eventEl = event.target.closest("[data-gcal-event-id]");
                if (eventEl) {
                    gcalOpenComposer(btn.getAttribute("data-gcal-date"), gcalClientTime({ slot_time: "09:00" }), eventEl.getAttribute("data-gcal-event-id"));
                    return;
                }
                const [year, month, day] = btn.getAttribute("data-gcal-date").split("-").map(Number);
                gcalVisibleDate = new Date(year, month - 1, day);
                gcalOpenComposer(btn.getAttribute("data-gcal-date"), "09:00");
            });
        });
        scheduleGridContainer.querySelectorAll(".gcal-day-column").forEach(column => {
            column.addEventListener("click", (event) => {
                if (event.target.closest(".gcal-column-add")) return;
                const eventEl = event.target.closest("[data-gcal-event-id]");
                if (eventEl) {
                    gcalOpenComposer(column.getAttribute("data-gcal-column-date"), "09:00", eventEl.getAttribute("data-gcal-event-id"));
                    return;
                }
                const rect = column.getBoundingClientRect();
                const y = Math.max(0, event.clientY - rect.top);
                const rawHour = GCAL2_START_HOUR + (y / GCAL2_HOUR_HEIGHT);
                const hour = Math.min(GCAL2_END_HOUR - 1, Math.max(GCAL2_START_HOUR, Math.floor(rawHour)));
                const minute = (rawHour - hour) >= 0.5 ? "30" : "00";
                gcalOpenComposer(column.getAttribute("data-gcal-column-date"), `${String(hour).padStart(2, "0")}:${minute}`);
            });
        });
        scheduleGridContainer.querySelectorAll("[data-gcal-mini-nav]").forEach(btn => {
            btn.addEventListener("click", () => {
                const amount = parseInt(btn.getAttribute("data-gcal-mini-nav"), 10);
                gcalVisibleDate = new Date(gcalVisibleDate.getFullYear(), gcalVisibleDate.getMonth() + amount, 1);
                renderSlots();
            });
        });
        scheduleGridContainer.querySelectorAll("[data-gcal-filter]").forEach(input => {
            input.addEventListener("change", () => {
                gcalFilters[input.getAttribute("data-gcal-filter")] = input.checked;
                renderSlots();
            });
        });
        scheduleGridContainer.querySelectorAll("[data-gcal-month]").forEach(btn => {
            btn.addEventListener("click", () => {
                gcalVisibleDate = new Date(gcalVisibleDate.getFullYear(), parseInt(btn.getAttribute("data-gcal-month"), 10), 1);
                gcalViewMode = "month";
                renderSlots();
            });
        });
        document.getElementById("gcal-toggle-weekends")?.addEventListener("change", (event) => {
            gcalShowWeekends = event.target.checked;
            renderSlots();
        });
        document.getElementById("gcal-toggle-cancelled")?.addEventListener("change", (event) => {
            gcalShowCancelled = event.target.checked;
            renderSlots();
        });
        document.getElementById("gcal-toggle-completed")?.addEventListener("change", (event) => {
            gcalShowCompleted = event.target.checked;
            renderSlots();
        });
        document.getElementById("gcal-create-slot")?.addEventListener("click", () => gcalOpenComposer(getISODate(gcalVisibleDate), "09:00"));
        scheduleGridContainer.querySelectorAll(".gcal-column-add").forEach(btn => {
            btn.addEventListener("click", (event) => {
                event.stopPropagation();
                gcalOpenComposer(btn.getAttribute("data-gcal-column-date") || getISODate(gcalVisibleDate), "09:00");
            });
        });
        document.getElementById("gcal-composer-close")?.addEventListener("click", () => {
            gcalComposer = null;
            renderSlots();
        });
        const serviceSelect = document.getElementById("gcal-composer-service");
        const customServiceRow = scheduleGridContainer.querySelector(".gcal-custom-service-row");
        serviceSelect?.addEventListener("change", () => {
            customServiceRow?.classList.toggle("is-hidden", serviceSelect.value !== "__other__");
            if (serviceSelect.value === "__other__") {
                document.getElementById("gcal-composer-custom-service")?.focus();
            }
        });
        document.getElementById("gcal-composer-delete")?.addEventListener("click", () => {
            if (!gcalComposer?.id) return;
            gcalCustomEvents = gcalCustomEvents.filter(item => item.id !== gcalComposer.id);
            gcalSaveCustomEvents();
            gcalComposer = null;
            renderSlots();
            showToast("Evento excluído", "O evento foi removido da agenda.", "success");
        });
        document.getElementById("gcal-composer-form")?.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!gcalComposer || gcalComposer.readOnly) return;
            const date = document.getElementById("gcal-composer-date").value || getISODate(gcalVisibleDate);
            const time = document.getElementById("gcal-composer-time").value || "09:00";
            const name = document.getElementById("gcal-composer-name").value.trim();
            const cpf = document.getElementById("gcal-composer-cpf").value.trim();
            const phone = document.getElementById("gcal-composer-phone").value.trim();
            const serviceSelect = document.getElementById("gcal-composer-service");
            const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
            const rawExamId = serviceSelect.value && serviceSelect.value !== "__other__" ? parseInt(serviceSelect.value, 10) : NaN;
            const examId = Number.isFinite(rawExamId) ? rawExamId : null;
            const customService = document.getElementById("gcal-composer-custom-service")?.value.trim() || "";
            const service = serviceSelect.value === "__other__"
                ? customService
                : (selectedOption?.dataset?.service || selectedOption?.textContent?.trim() || serviceSelect.dataset.currentService || "");

            if (!name || !cpf || !phone || !service) {
                showToast("Dados incompletos", "Informe nome, CPF, telefone e procedimento.", "error");
                return;
            }

            const [year, month, day] = date.split("-");
            const payload = {
                name,
                cpf,
                phone,
                source: "whatsapp",
                service,
                appointment_date: `${day}/${month}/${year} às ${time}`,
                slot_date: date,
                slot_time: time,
                upsell_success: false,
                upsell_service: null,
                status: "pending",
                exam_id: examId,
                needs_human: false
            };

            try {
                const res = await fetch(`${API_BASE}/api/clients`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.detail || "Nao foi possivel criar o agendamento.");
                }
                const savedClient = await res.json();
                allClients = [savedClient, ...allClients.filter(client => client.id !== savedClient.id)];
                gcalComposer = null;
                gcalVisibleDate = new Date(`${date}T00:00:00`);
                renderSlots();
                showToast("Agendamento criado", "O paciente foi adicionado a agenda.", "success");
            } catch (error) {
                console.error("Erro ao criar agendamento pela agenda:", error);
                showToast("Erro ao salvar", error.message || "Erro ao conectar com o servidor.", "error");
            }
        });
    }

    function renderSlots() {
        if (!scheduleGridContainer) return;
        const query = slotSearchInput ? slotSearchInput.value.toLowerCase().trim() : "";
        scheduleGridContainer.innerHTML = `
            <div class="gcal-app-shell">
                ${gcalSidebar()}
                <section class="gcal-main-panel">
                    <div class="gcal-toolbar gcal-toolbar-full">
                        <button type="button" class="gcal-icon-btn" title="Menu"><i class="fa-solid fa-bars"></i></button>
                        <div class="gcal-brand"><span>13</span><strong>Agenda</strong></div>
                        <button type="button" class="gcal-today-btn" id="gcal-today">Hoje</button>
                        <button type="button" class="gcal-nav-btn" id="gcal-prev" title="Anterior"><i class="fa-solid fa-chevron-left"></i></button>
                        <button type="button" class="gcal-nav-btn" id="gcal-next" title="Próximo"><i class="fa-solid fa-chevron-right"></i></button>
                        <h4>${gcalPeriodLabel()}</h4>
                        <button type="button" class="gcal-icon-btn" title="Pesquisar"><i class="fa-solid fa-magnifying-glass"></i></button>
                        <button type="button" class="gcal-icon-btn" title="Ajuda"><i class="fa-regular fa-circle-question"></i></button>
                        <button type="button" class="gcal-icon-btn" title="Configurações"><i class="fa-solid fa-gear"></i></button>
                        <div class="gcal-view-menu-wrap">
                            <button type="button" class="gcal-view-btn" id="gcal-view-button">${gcalViewLabel()} <i class="fa-solid fa-caret-down"></i></button>
                            ${gcalViewMenu()}
                        </div>
                    </div>
                    ${gcalRenderView(query)}
                    ${gcalComposerHtml()}
                </section>
            </div>
        `;
        gcalBindControls();
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
