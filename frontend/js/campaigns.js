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