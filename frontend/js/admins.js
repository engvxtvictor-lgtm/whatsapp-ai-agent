// 4. RENDERIZAR ADMINISTRADORES
    function renderAdmins() {
        adminsGrid.innerHTML = "";
        
        allAdmins.forEach(admin => {
            const card = document.createElement("div");
            card.className = "admin-card";
            card.style.position = "relative"; // Para os botões de ação absolutos, se necessário
            card.innerHTML = `
                <div style="position: absolute; top: 10px; right: 10px; display: flex; gap: 5px;">
                    <button class="btn-icon" onclick="editAdmin(${admin.id})" style="background:none; border:none; color:var(--gold-primary); cursor:pointer;"><i class="fa-solid fa-pen"></i></button>
                    <button class="btn-icon" onclick="deleteAdmin(${admin.id})" style="background:none; border:none; color:#ef4444; cursor:pointer;"><i class="fa-solid fa-trash"></i></button>
                </div>
                <img src="${admin.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=Lumina'}" alt="${admin.name}" class="admin-avatar">
                <h4 class="admin-name">${admin.name}</h4>
                <p class="admin-email">${admin.email}</p>
                <span class="admin-role-badge">${admin.role}</span>
            `;
            adminsGrid.appendChild(card);
        });
    }

    window.editAdmin = function(id) {
        const admin = allAdmins.find(a => a.id === id);
        if (!admin) return;
        
        document.getElementById("admin-id").value = admin.id;
        document.getElementById("admin-name").value = admin.name;
        document.getElementById("admin-email").value = admin.email;
        document.getElementById("admin-role").value = admin.role;
        
        document.getElementById("admin-modal-title").innerText = "Editar Administrador";
        document.getElementById("modal-admin").classList.add("active");
    };

    window.deleteAdmin = async function(id) {
        if (!confirm("Tem certeza que deseja remover este administrador?")) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/admins/${id}`, {
                method: "DELETE"
            });
            if (response.ok) {
                allAdmins = allAdmins.filter(a => a.id !== id);
                renderAdmins();
            } else {
                alert("Erro ao excluir administrador.");
            }
        } catch (error) {
            console.error("Erro delete admin:", error);
            alert("Erro de conexão com o servidor.");
        }
    };