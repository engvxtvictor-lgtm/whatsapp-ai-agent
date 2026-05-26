// 4. RENDERIZAR ADMINISTRADORES
    function renderAdmins() {
        adminsGrid.innerHTML = "";
        
        allAdmins.forEach(admin => {
            const card = document.createElement("div");
            card.className = "admin-card";
            card.innerHTML = `
                <img src="${admin.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=Lumina'}" alt="${admin.name}" class="admin-avatar">
                <h4 class="admin-name">${admin.name}</h4>
                <p class="admin-email">${admin.email}</p>
                <span class="admin-role-badge">${admin.role}</span>
            `;
            adminsGrid.appendChild(card);
        });
    }