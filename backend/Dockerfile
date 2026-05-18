FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema necessárias para PostgreSQL e compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala dependências do Python
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código-fonte
COPY . .

EXPOSE 8000

# Executa o servidor FastAPI com suporte a auto-reload
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
