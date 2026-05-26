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