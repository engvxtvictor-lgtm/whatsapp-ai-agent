// 7.5. GERENCIAMENTO DE EXAMES (TABELA DE EXAMES & VALORES)
    const examSearchInput = document.getElementById("exam-search");
    const examsTableBody = document.getElementById("exams-table-body");
    const modalExam = document.getElementById("modal-exam");
    const btnAddExamModal = document.getElementById("btn-add-exam-modal");
    const btnCloseExamModal = document.getElementById("btn-close-exam-modal");
    const btnCancelExamModal = document.getElementById("btn-cancel-exam-modal");
    const formAddExam = document.getElementById("form-add-exam");
    const examIdInput = document.getElementById("exam-id");
    const examNameInput = document.getElementById("exam-name");
    const examPriceInput = document.getElementById("exam-price");
    const examCategorySelect = document.getElementById("exam-category");
    const btnSubmitExam = document.getElementById("btn-submit-exam");
    const examModalTitle = document.getElementById("exam-modal-title");

    if (btnAddExamModal) {
        btnAddExamModal.addEventListener("click", () => {
            examModalTitle.innerText = "Adicionar Procedimento";
            btnSubmitExam.innerText = "Cadastrar Procedimento";
            formAddExam.reset();
            examIdInput.value = "";
            modalExam.classList.add("active");
        });
    }

    if (btnCloseExamModal) {
        btnCloseExamModal.addEventListener("click", () => {
            modalExam.classList.remove("active");
            formAddExam.reset();
        });
    }

    if (btnCancelExamModal) {
        btnCancelExamModal.addEventListener("click", () => {
            modalExam.classList.remove("active");
            formAddExam.reset();
        });
    }

    if (examSearchInput) {
        examSearchInput.addEventListener("input", renderExams);
    }

    function renderExams() {
        if (!examsTableBody) return;
        examsTableBody.innerHTML = "";

        const query = examSearchInput ? examSearchInput.value.toLowerCase().trim() : "";

        const filtered = allExams.filter(exam => {
            return exam.name.toLowerCase().includes(query) || 
                   exam.category.toLowerCase().includes(query);
        });

        if (filtered.length === 0) {
            examsTableBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 30px; color: rgba(255,255,255,0.4);">
                        <i class="fa-regular fa-folder-open" style="font-size: 24px; margin-bottom: 8px; display: block;"></i>
                        Nenhum exame ou procedimento encontrado.
                    </td>
                </tr>
            `;
            return;
        }

        // Ordena por categoria e depois por nome
        filtered.sort((a, b) => {
            const catCompare = a.category.localeCompare(b.category);
            if (catCompare !== 0) return catCompare;
            return a.name.localeCompare(b.name);
        });

        filtered.forEach(exam => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${exam.name}</strong></td>
                <td><span class="badge-category ${getCategoryClass(exam.category)}"><i class="fa-solid fa-tag"></i> ${exam.category}</span></td>
                <td>R$ ${exam.price.toFixed(2).replace('.', ',')}</td>
                <td>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-secondary-outline btn-xs btn-edit-exam" data-id="${exam.id}" title="Editar">
                            <i class="fa-solid fa-pencil"></i>
                        </button>
                        <button class="btn btn-danger-outline btn-xs btn-delete-exam" data-id="${exam.id}" style="color: #ef4444; border-color: rgba(239, 68, 68, 0.2);" title="Excluir">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;

            // Clique no botão Editar
            tr.querySelector(".btn-edit-exam").addEventListener("click", () => {
                examModalTitle.innerText = "Editar Procedimento";
                btnSubmitExam.innerText = "Salvar Alterações";
                examIdInput.value = exam.id;
                examNameInput.value = exam.name;
                examPriceInput.value = exam.price;
                examCategorySelect.value = exam.category;
                modalExam.classList.add("active");
            });

            // Clique no botão Excluir
            tr.querySelector(".btn-delete-exam").addEventListener("click", async () => {
                if (confirm(`Deseja realmente excluir o procedimento "${exam.name}"?`)) {
                    try {
                        const res = await fetch(`${API_BASE}/api/exams/${exam.id}`, {
                            method: "DELETE"
                        });
                        if (res.ok) {
                            allExams = allExams.filter(e => e.id !== exam.id);
                            renderExams();
                            populateServiceSelects();
                        } else {
                            alert("Falha ao excluir o procedimento.");
                        }
                    } catch (error) {
                        console.error("Erro ao deletar exame:", error);
                        alert("Erro de conexão com o servidor.");
                    }
                }
            });

            examsTableBody.appendChild(tr);
        });
    }

    if (formAddExam) {
        formAddExam.addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = examIdInput.value;
            const name = examNameInput.value.trim();
            const price = parseFloat(examPriceInput.value);
            const category = examCategorySelect.value;

            const payload = { name, price, category };

            const isEdit = id !== "";
            const url = isEdit ? `${API_BASE}/api/exams/${id}` : `${API_BASE}/api/exams`;
            const method = isEdit ? "PUT" : "POST";

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const savedExam = await res.json();
                    if (isEdit) {
                        allExams = allExams.map(e => e.id === savedExam.id ? savedExam : e);
                    } else {
                        allExams.push(savedExam);
                    }
                    renderExams();
                    populateServiceSelects();
                    modalExam.classList.remove("active");
                    formAddExam.reset();
                } else {
                    alert(`Erro ao ${isEdit ? 'atualizar' : 'cadastrar'} o procedimento.`);
                }
            } catch (error) {
                console.error("Erro ao salvar exame:", error);
                alert("Erro de conexão com o servidor.");
            }
        });
    }