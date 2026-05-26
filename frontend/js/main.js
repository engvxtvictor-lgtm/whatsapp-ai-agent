// 8. CARREGAMENTO DOS DADOS
    async function loadData() {
        try {
            const [clientsRes, adminsRes, examsRes, slotsRes] = await Promise.all([
                fetch(`${API_BASE}/api/clients`),
                fetch(`${API_BASE}/api/admins`),
                fetch(`${API_BASE}/api/exams`),
                fetch(`${API_BASE}/api/slots`)
            ]);

            if (clientsRes.ok && adminsRes.ok && examsRes.ok && slotsRes.ok) {
                allClients = await clientsRes.json();
                allAdmins = await adminsRes.json();
                allExams = await examsRes.json();
                allSlots = await slotsRes.json();

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

    // Inicialização
    loadData();

    // Polling a cada 5 segundos para atualizar dados e checar atendimento humano
    setInterval(loadData, 5000);