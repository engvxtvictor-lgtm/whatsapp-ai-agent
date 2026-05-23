-- Criação das tabelas para o banco de dados PostgreSQL do Sistema

-- Tabela de Exames e Procedimentos
CREATE TABLE IF NOT EXISTS web_exams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Clientes
CREATE TABLE IF NOT EXISTS web_clients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    cpf VARCHAR(14) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    source VARCHAR(20) DEFAULT 'whatsapp',
    service VARCHAR(50) NOT NULL,
    profile_pic VARCHAR(255),
    
    -- Novos campos para agendamento e upsell
    appointment_date VARCHAR(100),
    upsell_success BOOLEAN DEFAULT FALSE NOT NULL,
    upsell_service VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    exam_id INTEGER REFERENCES web_exams(id),
    needs_human BOOLEAN DEFAULT FALSE NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Administradores
CREATE TABLE IF NOT EXISTS web_admins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    avatar VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Serviços
CREATE TABLE IF NOT EXISTS web_services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    necessity TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Automação de Follow-Up
CREATE TABLE IF NOT EXISTS web_followups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    service VARCHAR(50) NOT NULL,
    delay_days INTEGER NOT NULL,
    message_template VARCHAR(500) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inserção de dados iniciais para testes
INSERT INTO web_admins (name, email, role, avatar)
VALUES 
('Dra. Ana Souza', 'ana.souza@odontoclinic.com', 'Dentista Principal', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Ana'),
('Carlos Eduardo', 'carlos.eduardo@odontoclinic.com', 'Administrador', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Carlos'),
('Mariana Lima', 'mariana.lima@odontoclinic.com', 'Atendente', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Mariana')
ON CONFLICT DO NOTHING;

-- Inserção de Exames/Procedimentos
INSERT INTO web_exams (name, price, category)
VALUES
('Raspagem (Limpeza)', 120.00, 'Prevenção'),
('Consulta + Aplicação de Flúor Infantil', 50.00, 'Odontopediatria'),
('Radiografia Periapical', 35.00, 'Diagnóstico'),
('Restauração', 80.00, 'Clínico Geral'),
('Restauração Infantil', 70.00, 'Odontopediatria'),
('Extração Infantil', 90.00, 'Odontopediatria'),
('Extração Simples', 120.00, 'Cirurgia'),
('Tratamento de Canal', 600.00, 'Endodontia'),
('Facetas (por dente)', 250.00, 'Estética'),
('Prótese Dentária', 950.00, 'Prótese'),
('Pino + Coroa', 500.00, 'Prótese'),
('Manutenção Aparelho', 90.00, 'Ortodontia'),
('Clareamento (por sessão)', 250.00, 'Estética'),
('Placa para Bruxismo', 450.00, 'Clínico Geral'),
('Contenção Ortodôntica Inferior', 200.00, 'Ortodontia'),
('Contenção Ortodôntica Superior', 250.00, 'Ortodontia'),
('Implante', 2800.00, 'Implantodontia'),
('Gengivoplastia (por dente)', 200.00, 'Periodontia'),
('Remoção de Facetas', 300.00, 'Estética'),
('Extração Complexa (Siso)', 300.00, 'Cirurgia')
ON CONFLICT DO NOTHING;

INSERT INTO web_clients (name, cpf, phone, source, service, profile_pic, appointment_date, upsell_success, upsell_service, status, exam_id)
VALUES 
('Rodrigo Silva', '123.456.789-00', '5511988888888', 'whatsapp', 'Clareamento (por sessão)', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Rodrigo', '25/05/2026 as 14:00', TRUE, 'Raspagem (Limpeza)', 'confirmed', 13),
('Beatriz Santos', '987.654.321-11', '5511977777777', 'instagram', 'Raspagem (Limpeza)', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz', '28/05/2026 as 10:30', FALSE, NULL, 'pending', 1),
('Felipe Oliveira', '456.789.123-22', '5511966666666', 'whatsapp', 'Implante', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Felipe', '01/06/2026 as 16:00', TRUE, 'Pino + Coroa', 'confirmed', 17)
ON CONFLICT DO NOTHING;

INSERT INTO web_services (name, price, necessity)
VALUES
('Limpeza Completa', 150.00, 'Recomendado realizar a cada 6 meses para remover tartaro e placas bacterianas, prevenindo gengivite e mantendo a saude bucal em dia.'),
('Clareamento Dental', 600.00, 'Indicado para pacientes que buscam melhorar a estetica do sorriso, clarear dentes amarelados ou remover manchas externas.'),
('Aparelho Ortodontico', 1500.00, 'Indicado para alinhar dentes tortos ou apinhados, corrigir a mordida desalinhada e melhorar a harmonia e funcionalidade da arcada dentaria.'),
('Implante Dentario', 2500.00, 'Indicado para reabilitar dentes ausentes, permitindo recuperar a mastigacao perfeita e a estetica do sorriso com uma protese fixa ultra-resistente.'),
('Protese Provisoria', 400.00, 'Indicada para proteger o dente preparado e garantir a estetica e mastigacao temporaria enquanto a protese definitiva esta sendo fabricada no laboratorio.')
ON CONFLICT DO NOTHING;

INSERT INTO web_followups (name, service, delay_days, message_template, is_active)
VALUES
('Lembrete Semestral', 'Limpeza', 180, 'Olá [NOME]! Identificamos que já faz 6 meses desde o seu último procedimento de [SERVIÇO]. Que tal agendarmos um retorno preventivo esta semana?', TRUE),
('Acompanhamento Pós-Cirúrgico', 'Implante', 1, 'Olá [NOME], como está a recuperação do seu procedimento de [SERVIÇO]? Qualquer desconforto ou dúvida, estamos aqui!', TRUE),
('Feedback de Sensibilidade', 'Clareamento', 3, 'Olá [NOME], sentiu alguma sensibilidade após a sessão de [SERVIÇO]? Lembre-se de evitar alimentos corantes hoje!', TRUE)
ON CONFLICT DO NOTHING;

