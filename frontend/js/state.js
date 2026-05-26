// Estado Global do Frontend
    let allClients = [];
    let allAdmins = [];
    let allExams = [];
    let allSlots = [];
    const selectedClients = new Set();
    const activeHumanRequests = new Set();

    // Referências do DOM
    const tabNavItems = document.querySelectorAll(".nav-item");
    const tabPanels = document.querySelectorAll(".tab-panel");
    const pageTitle = document.getElementById("page-title");
    const pageDescription = document.getElementById("page-description");

    const clientsGrid = document.getElementById("clients-grid");
    const adminsGrid = document.getElementById("admins-grid");

    // Inputs de Filtros e Busca
    const clientSearchInput = document.getElementById("client-search");
    const filterServiceSelect = document.getElementById("filter-service");
    const filterSourceSelect = document.getElementById("filter-source");

    // Métricas
    const metricTotalClients = document.getElementById("metric-total-clients");
    const metricWaClients = document.getElementById("metric-wa-clients");
    const metricIgClients = document.getElementById("metric-ig-clients");
    const metricSelectedClients = document.getElementById("metric-selected-clients");

    // Seleção em lote bar
    const batchActionBar = document.querySelector(".batch-action-bar");
    const batchSelectionText = document.getElementById("batch-selection-text");
    const btnSelectAll = document.getElementById("btn-select-all");
    const btnClearSelection = document.getElementById("btn-clear-selection");
    const btnSendCampaignFromSelection = document.getElementById("btn-send-campaign-from-selection");

    // Modais
    const modalClient = document.getElementById("modal-client");
    const modalAdmin = document.getElementById("modal-admin");
    const modalSlot = document.getElementById("modal-slot");
    const btnAddClientModal = document.getElementById("btn-add-client-modal");
    const btnAddAdminModal = document.getElementById("btn-add-admin-modal");
    const btnAddSlotModal = document.getElementById("btn-add-slot-modal");

    // Slots refs
    const btnCloseSlotModal = document.getElementById("btn-close-slot-modal");
    const btnCancelSlotModal = document.getElementById("btn-cancel-slot-modal");
    const formAddSlot = document.getElementById("form-add-slot");
    const scheduleGridContainer = document.getElementById("schedule-grid-container");
    const slotSearchInput = document.getElementById("slot-search");

    // Fechar Modais
    const btnCloseClientModal = document.getElementById("btn-close-client-modal");
    const btnCancelClientModal = document.getElementById("btn-cancel-client-modal");
    const btnCloseAdminModal = document.getElementById("btn-close-admin-modal");
    const btnCancelAdminModal = document.getElementById("btn-cancel-admin-modal");

    // Formulários
    const formAddClient = document.getElementById("form-add-client");
    const formAddAdmin = document.getElementById("form-add-admin");

    // Painel de Campanha
    const campaignMessageTextarea = document.getElementById("campaign-message");
    const btnSubmitCampaign = document.getElementById("btn-submit-campaign");
    const quickTemplatePills = document.querySelectorAll(".template-pill");
    const campaignSelectedCountTitle = document.getElementById("campaign-selected-count-title");
    const campaignSelectedCountDesc = document.getElementById("campaign-selected-count-desc");

    // Helper to normalize and get Category HSL Badge Class
    function getCategoryClass(category) {
        if (!category) return 'badge-cat-none';
        const normalized = category.toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "") // remove accents
            .replace(/\s+/g, '-') // spaces to hyphen
            .replace(/[^a-z0-9\-]/g, ''); // keep alphanumeric and hyphen
        return `badge-cat-${normalized}`;
    }