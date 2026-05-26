import os, re

with open('app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the outer DOMContentLoaded wrapper
start_idx = content.find('document.addEventListener("DOMContentLoaded", () => {')
if start_idx != -1:
    content = content[:start_idx] + content[start_idx + len('document.addEventListener("DOMContentLoaded", () => {'):]
    # Remove the last '});'
    last_idx = content.rfind('});')
    if last_idx != -1:
        content = content[:last_idx] + content[last_idx + len('});'):]

# Split by sections
sections = [
    ('auth.js', '// 0. AUTENTICAÇÃO / LOGIN', '// Estado Global do Frontend'),
    ('state.js', '// Estado Global do Frontend', '// 1. NAVEGAÇÃO DE ABAS'),
    ('nav.js', '// 1. NAVEGAÇÃO DE ABAS', '// 2. BUSCAR E FILTRAR PACIENTES (CLIENTES)'),
    ('clients.js', '// 2. BUSCAR E FILTRAR PACIENTES (CLIENTES)', '// 4. RENDERIZAR ADMINISTRADORES'),
    ('admins.js', '// 4. RENDERIZAR ADMINISTRADORES', '// 5. ENVIAR CAMPANHAS E TEMPLATES'),
    ('campaigns.js', '// 5. ENVIAR CAMPANHAS E TEMPLATES', '// 6. GERENCIAMENTO DE MODAIS E CADASTROS'),
    ('modals.js', '// 6. GERENCIAMENTO DE MODAIS E CADASTROS', '// 7. GERENCIAMENTO DE AUTOMACÕES DE FOLLOW-UP'),
    ('followups.js', '// 7. GERENCIAMENTO DE AUTOMACÕES DE FOLLOW-UP', '// 7.5. GERENCIAMENTO DE EXAMES (TABELA DE EXAMES & VALORES)'),
    ('exams.js', '// 7.5. GERENCIAMENTO DE EXAMES (TABELA DE EXAMES & VALORES)', '// 7.7. GERENCIAMENTO DE SLOTS (AGENDA)'),
    ('schedule.js', '// 7.7. GERENCIAMENTO DE SLOTS (AGENDA)', '// 8. CARREGAMENTO DOS DADOS'),
    ('main.js', '// 8. CARREGAMENTO DOS DADOS', None),
]

for name, start_str, end_str in sections:
    start_idx = content.find(start_str)
    if end_str:
        end_idx = content.find(end_str)
        part = content[start_idx:end_idx]
    else:
        part = content[start_idx:]
    
    with open(f'js/{name}', 'w', encoding='utf-8') as out:
        out.write(part.strip())

print('JS splitted successfully.')
