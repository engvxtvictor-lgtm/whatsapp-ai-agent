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

-- Inserção de dados iniciais para testes (Opcional)
INSERT INTO web_admins (name, email, role, avatar)
VALUES 
('Dra. Ana Souza', 'ana.souza@odontoclinic.com', 'Dentista Principal', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Ana'),
('Carlos Eduardo', 'carlos.eduardo@odontoclinic.com', 'Administrador', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Carlos'),
('Mariana Lima', 'mariana.lima@odontoclinic.com', 'Atendente', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Mariana')
ON CONFLICT DO NOTHING;

INSERT INTO web_clients (name, cpf, phone, source, service, profile_pic)
VALUES 
('Rodrigo Silva', '123.456.789-00', '5511988888888', 'whatsapp', 'Clareamento Dental', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Rodrigo'),
('Beatriz Santos', '987.654.321-11', '5511977777777', 'instagram', 'Limpeza e Profilaxia', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz'),
('Felipe Oliveira', '456.789.123-22', '5511966666666', 'whatsapp', 'Implante Dentario', 'https://api.dicebear.com/7.x/adventurer/svg?seed=Felipe')
ON CONFLICT DO NOTHING;
