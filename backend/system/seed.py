import os
import sys
import asyncio

# Adiciona o diretório raiz ao PYTHONPATH antes de importar os módulos locais
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select
from backend.system.database import AsyncSession, engine, Base
from backend.system.models.web_models import ClientWeb, AdminWeb

async def seed_db():
    print("Iniciando semeadura do banco de dados...")
    
    # Recria as tabelas (deleta se existirem para aplicar a nova estrutura)
    async with engine.begin() as conn:
        print("Recriando tabelas...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession() as session:
        # Criando administradores padrão
        print("Criando administradores padrao...")
        admins = [
            AdminWeb(
                name="Dra. Ana Souza",
                email="ana.souza@odontoclinic.com",
                role="Dentista Principal",
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Ana"
            ),
            AdminWeb(
                name="Carlos Eduardo",
                email="carlos.eduardo@odontoclinic.com",
                role="Administrador",
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Carlos"
            ),
            AdminWeb(
                name="Mariana Lima",
                email="mariana.lima@odontoclinic.com",
                role="Atendente",
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Mariana"
            )
        ]
        session.add_all(admins)

        # Criando clientes padrão com novos campos
        print("Criando clientes padrao...")
        clients = [
            ClientWeb(
                name="Rodrigo Silva",
                cpf="123.456.789-00",
                phone="5511988888888",
                source="whatsapp",
                service="Clareamento Dental",
                profile_pic="https://api.dicebear.com/7.x/adventurer/svg?seed=Rodrigo",
                appointment_date="25/05/2026 as 14:00",
                upsell_success=True,
                upsell_service="Limpeza Completa"
            ),
            ClientWeb(
                name="Beatriz Santos",
                cpf="987.654.321-11",
                phone="5511977777777",
                source="instagram",
                service="Limpeza e Profilaxia",
                profile_pic="https://api.dicebear.com/7.x/adventurer/svg?seed=Beatriz",
                appointment_date="28/05/2026 as 10:30",
                upsell_success=False,
                upsell_service=None
            ),
            ClientWeb(
                name="Felipe Oliveira",
                cpf="456.789.123-22",
                phone="5511966666666",
                source="whatsapp",
                service="Implante Dentario",
                profile_pic="https://api.dicebear.com/7.x/adventurer/svg?seed=Felipe",
                appointment_date="01/06/2026 as 16:00",
                upsell_success=True,
                upsell_service="Protese Provisoria"
            )
        ]
        session.add_all(clients)
        await session.commit()
            
    print("Semeadura concluida!")

if __name__ == "__main__":
    asyncio.run(seed_db())
