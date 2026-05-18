-- Criação das tabelas para o banco de dados PostgreSQL do Sistema

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

-- Inserção de dados iniciais para testes
INSERT INTO web_admins (name, email, role, avatar)
VALUES 
('Dra. Ana Souza', 'ana.souza@odontoclinic.com', 'Dentista Principal', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Ana'),
('Carlos Eduardo', 'carlos.eduardo@odontoclinic.com', 'Administrador', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Carlos'),
('Mariana Lima', 'mariana.lima@odontoclinic.com', 'Atendente', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Mariana')
ON CONFLICT DO NOTHING;

INSERT INTO web_clients (name, cpf, phone, source, service, profile_pic, appointment_date, upsell_success, upsell_service)
VALUES 
('Rodrigo Silva', '123.456.789-00', '5511988888888', 'whatsapp', 'Clareamento Dental', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Rodrigo', '25/05/2026 as 14:00', TRUE, 'Limpeza Completa'),
('Beatriz Santos', '987.654.321-11', '5511977777777', 'instagram', 'Limpeza e Profilaxia', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz', '28/05/2026 as 10:30', FALSE, NULL),
('Felipe Oliveira', '456.789.123-22', '5511966666666', 'whatsapp', 'Implante Dentario', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Felipe', '01/06/2026 as 16:00', TRUE, 'Protese Provisoria')
ON CONFLICT DO NOTHING;

INSERT INTO web_services (name, price, necessity)
VALUES
('Limpeza Completa', 150.00, 'Recomendado realizar a cada 6 meses para remover tartaro e placas bacterianas, prevenindo gengivite e mantendo a saude bucal em dia.'),
('Clareamento Dental', 600.00, 'Indicado para pacientes que buscam melhorar a estetica do sorriso, clarear dentes amarelados ou remover manchas externas.'),
('Aparelho Ortodontico', 1500.00, 'Indicado para alinhar dentes tortos ou apinhados, corrigir a mordida desalinhada e melhorar a harmonia e funcionalidade da arcada dentaria.'),
('Implante Dentario', 2500.00, 'Indicado para reabilitar dentes ausentes, permitindo recuperar a mastigacao perfeita e a estetica do sorriso com uma protese fixa ultra-resistente.'),
('Protese Provisoria', 400.00, 'Indicada para proteger o dente preparado e garantir a estetica e mastigacao temporaria enquanto a protese definitiva esta sendo fabricada no laboratorio.')
ON CONFLICT DO NOTHING;
