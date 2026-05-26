// 8. CARREGAMENTO DOS DADOS (E POPULADOR AUTOMÁTICO SE BANCO VAZIO)
    async function loadData() {
        try {
            const [clientsRes, adminsRes, examsRes, slotsRes] = await Promise.all([
                fetch("/api/clients"),
                fetch("/api/admins"),
                fetch("/api/exams"),
                fetch("/api/slots")
            ]);

            if (clientsRes.ok && adminsRes.ok && examsRes.ok && slotsRes.ok) {
                allClients = await clientsRes.json();
                allAdmins = await adminsRes.json();
                allExams = await examsRes.json();
                allSlots = await slotsRes.json();

                // Se o banco estiver vazio, populate com dados realistas da Clínica Lúmina automaticamente!
                if (allClients.length === 0 && allAdmins.length === 0) {
                    console.log("Banco de dados vazio detectado. Populando banco local com dados reais...");
                    await populateInitialDatabase();
                    return; // populateInitialDatabase fará o recarregamento
                }

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

    async function populateInitialDatabase() {
        const mockClients = [
            { name: "Ana Maria Silva", cpf: "123.456.789-10", phone: "5511999999999", service: "Limpeza", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Ana", appointment_date: "25/05/2026 às 14:00", upsell_success: true, upsell_service: "Clareamento", status: "confirmed" },
            { name: "Carlos Eduardo Costa", cpf: "987.654.321-00", phone: "5511988888888", service: "Implante", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Carlos", appointment_date: "28/05/2026 às 10:30", upsell_success: false, upsell_service: null, status: "confirmed" },
            { name: "Mariana Souza", cpf: "456.789.123-45", phone: "5511977777777", service: "Clareamento", source: "instagram", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Mariana", appointment_date: "01/06/2026 às 16:00", upsell_success: true, upsell_service: "Profilaxia", status: "confirmed" },
            { name: "Guilherme Santos", cpf: "321.654.987-12", phone: "5511966666666", service: "Aparelho", source: "whatsapp", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Guilherme", appointment_date: null, upsell_success: false, upsell_service: null, status: "pending" },
            { name: "Beatriz Ramos", cpf: "654.123.987-00", phone: "5511955555555", service: "Canal", source: "instagram", profile_pic: "https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz", appointment_date: null, upsell_success: false, upsell_service: null, status: "pending" }
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

    // Polling a cada 5 segundos para atualizar dados e checar atendimento humano
    setInterval(loadData, 5000);