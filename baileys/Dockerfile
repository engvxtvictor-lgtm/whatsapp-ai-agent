FROM node:18-slim

WORKDIR /app

# Instala dependências básicas do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copia arquivos de dependência do npm
COPY package*.json ./

# Instala as dependências de produção do Node.js
RUN npm ci --only=production

# Copia o restante do código do Baileys
COPY . .

# Cria pasta de autenticação se não existir
RUN mkdir -p auth

EXPOSE 3000

# Executa o serviço Baileys
CMD ["node", "index.js"]
