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