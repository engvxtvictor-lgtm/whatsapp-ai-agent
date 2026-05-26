import os

with open('style.css', 'r', encoding='utf-8') as f:
    content = f.read()

sections = [
    ('variables.css', '/* CSS Customizado - Clínica Lúmina */', '/* 1. Sidebar ("Prateleira") */'),
    ('sidebar.css', '/* 1. Sidebar ("Prateleira") */', '/* 2. Main Content Area */'),
    ('layout.css', '/* 2. Main Content Area */', '/* 6. Control Bar e Filtros */'),
    ('components.css', '/* 6. Control Bar e Filtros */', '/* 8. Grid de Pacientes (Cards Quadradinhos) */'),
    ('clients.css', '/* 8. Grid de Pacientes (Cards Quadradinhos) */', '/* 9. Equipe & Admins */'),
    ('admins.css', '/* 9. Equipe & Admins */', '/* 10. Campanhas Layout Split */'),
    ('campaigns.css', '/* 10. Campanhas Layout Split */', '/* 11. Modais */'),
    ('modals.css', '/* 11. Modais */', '/* --- LOGIN OVERLAY --- */'),
    ('login.css', '/* --- LOGIN OVERLAY --- */', '/* --- BADGES ADICIONAIS --- */'),
    ('badges_actions.css', '/* --- BADGES ADICIONAIS --- */', '/* Tabela de Exames - Estilos Premium */'),
    ('exams_schedule.css', '/* Tabela de Exames - Estilos Premium */', None)
]

main_css = ''
for name, start_str, end_str in sections:
    start_idx = content.find(start_str)
    if end_str:
        end_idx = content.find(end_str)
        part = content[start_idx:end_idx]
    else:
        part = content[start_idx:]
    
    with open(f'css/{name}', 'w', encoding='utf-8') as out:
        out.write(part)
    
    main_css += f'@import url("{name}");\n'

with open('css/main.css', 'w', encoding='utf-8') as out:
    out.write(main_css)

print('CSS splitted successfully.')
