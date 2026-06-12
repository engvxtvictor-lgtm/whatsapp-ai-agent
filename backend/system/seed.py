import os
import sys
import asyncio

# Adiciona o diretório raiz ao PYTHONPATH antes de importar os módulos locais
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.system.database import AsyncSession, engine, Base
from backend.system.models.web_models import ClientWeb, AdminWeb, ServiceWeb, FollowupWeb, ExamWeb, ScheduleSlotWeb
from backend.system.auth import get_password_hash

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
        # Senha padrão para seed: admin123 (MUDE EM PRODUÇÃO usando create_admin.py)
        default_password_hash = get_password_hash("admin123")
        admins = [
            AdminWeb(
                name="Dra. Ana Souza",
                email="ana.souza@clinicalumina.com",
                role="Dentista Principal",
                password_hash=default_password_hash,
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Ana"
            ),
            AdminWeb(
                name="Carlos Eduardo",
                email="carlos.eduardo@clinicalumina.com",
                role="Administrador",
                password_hash=default_password_hash,
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Carlos"
            ),
            AdminWeb(
                name="Mariana Lima",
                email="mariana.lima@clinicalumina.com",
                role="Atendente",
                password_hash=default_password_hash,
                avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Mariana"
            )
        ]
        session.add_all(admins)

        # Criando exames/procedimentos padrão
        print("Criando exames padrao...")
        exams = [
            ExamWeb(name="Raspagem (Limpeza)", price=120.00, category="Prevenção"),
            ExamWeb(name="Consulta + Aplicação de Flúor Infantil", price=50.00, category="Odontopediatria"),
            ExamWeb(name="Radiografia Periapical", price=35.00, category="Diagnóstico"),
            ExamWeb(name="Restauração", price=80.00, category="Clínico Geral"),
            ExamWeb(name="Restauração Infantil", price=70.00, category="Odontopediatria"),
            ExamWeb(name="Extração Infantil", price=90.00, category="Odontopediatria"),
            ExamWeb(name="Extração Simples", price=120.00, category="Cirurgia"),
            ExamWeb(name="Tratamento de Canal", price=600.00, category="Endodontia"),
            ExamWeb(name="Facetas (por dente)", price=250.00, category="Estética"),
            ExamWeb(name="Prótese Dentária", price=950.00, category="Prótese"),
            ExamWeb(name="Pino + Coroa", price=500.00, category="Prótese"),
            ExamWeb(name="Manutenção Aparelho", price=90.00, category="Ortodontia"),
            ExamWeb(name="Clareamento (por sessão)", price=250.00, category="Estética"),
            ExamWeb(name="Placa para Bruxismo", price=450.00, category="Clínico Geral"),
            ExamWeb(name="Contenção Ortodôntica Inferior", price=200.00, category="Ortodontia"),
            ExamWeb(name="Contenção Ortodôntica Superior", price=250.00, category="Ortodontia"),
            ExamWeb(name="Implante", price=2800.00, category="Implantodontia"),
            ExamWeb(name="Gengivoplastia (por dente)", price=200.00, category="Periodontia"),
            ExamWeb(name="Remoção de Facetas", price=300.00, category="Estética"),
            ExamWeb(name="Extração Complexa (Siso)", price=300.00, category="Cirurgia")
        ]
        session.add_all(exams)
        await session.flush() # Gera os IDs para os exames antes de linkar os clientes

        # Criando clientes padrão com novos campos
        print("Criando clientes padrao...")
        clients = [
            ClientWeb(
                name="Rodrigo Silva",
                cpf="123.456.789-00",
                phone="5511988888888",
                source="whatsapp",
                service="Clareamento (por sessão)",
                appointment_date="25/05/2026 as 14:00",
                upsell_success=True,
                upsell_service="Raspagem (Limpeza)",
                status="confirmed",
                exam_id=exams[12].id
            ),
            ClientWeb(
                name="Beatriz Santos",
                cpf="987.654.321-11",
                phone="5511977777777",
                source="instagram",
                service="Raspagem (Limpeza)",
                appointment_date="28/05/2026 as 10:30",
                upsell_success=False,
                upsell_service=None,
                status="pending",
                exam_id=exams[0].id
            ),
            ClientWeb(
                name="Felipe Oliveira",
                cpf="456.789.123-22",
                phone="5511966666666",
                source="whatsapp",
                service="Implante",
                appointment_date="01/06/2026 as 16:00",
                upsell_success=True,
                upsell_service="Pino + Coroa",
                status="confirmed",
                exam_id=exams[16].id
            )
        ]
        session.add_all(clients)

        # Criando serviços padrão
        print("Criando servicos padrao...")
        services = [
            ServiceWeb(
                name="Limpeza Completa",
                price=150.00,
                necessity="Recomendado realizar a cada 6 meses para remover tartaro e placas bacterianas, prevenindo gengivite e mantendo a saude bucal em dia."
            ),
            ServiceWeb(
                name="Clareamento Dental",
                price=600.00,
                necessity="Indicado para pacientes que buscam melhorar a estetica do sorriso, clarear dentes amarelados ou remover manchas externas."
            ),
            ServiceWeb(
                name="Aparelho Ortodontico",
                price=1500.00,
                necessity="Indicado para alinhar dentes tortos ou apinhados, corrigir a mordida desalinhada e melhorar a harmonia e funcionalidade da arcada dentaria."
            ),
            ServiceWeb(
                name="Implante Dentario",
                price=2500.00,
                necessity="Indicado para reabilitar dentes ausentes, permitindo recuperar a mastigacao perfeita e a estetica do sorriso com uma protese fixa ultra-resistente."
            ),
            ServiceWeb(
                name="Protese Provisoria",
                price=400.00,
                necessity="Indicada para proteger o dente preparado e garantir a estetica e mastigacao temporaria enquanto a protese definitiva esta sendo fabricada no laboratorio."
            )
        ]
        session.add_all(services)

        # Criando regras de follow-up padrão
        print("Criando regras de follow-up padrao...")
        followups = [
            FollowupWeb(
                name="Lembrete Semestral",
                service="Limpeza",
                delay_days=180,
                message_template="Olá [NOME]! Identificamos que já faz 6 meses desde o seu último procedimento de [SERVIÇO]. Que tal agendarmos um retorno preventivo esta semana?",
                is_active=True
            ),
            FollowupWeb(
                name="Acompanhamento Pós-Cirúrgico",
                service="Implante",
                delay_days=1,
                message_template="Olá [NOME], como está a recuperação do seu procedimento de [SERVIÇO]? Qualquer desconforto ou dúvida, estamos aqui!",
                is_active=True
            ),
            FollowupWeb(
                name="Feedback de Sensibilidade",
                service="Clareamento",
                delay_days=3,
                message_template="Olá [NOME], sentiu alguma sensibilidade após a sessão de [SERVIÇO]? Lembre-se de evitar alimentos corantes hoje!",
                is_active=True
            )
        ]
        session.add_all(followups)

        # Criando slots de agendamento padrão (Seg-Sex, 08h às 18h)
        print("Criando slots de agendamento padrao...")
        slots = []
        for weekday in range(5):  # 0=Seg, 4=Sex
            for hour in ["08:00", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00", "18:00"]:
                slots.append(
                    ScheduleSlotWeb(
                        weekday=weekday,
                        time_str=hour,
                        max_patients=1,
                        is_active=True
                    )
                )
        session.add_all(slots)
        await session.commit()
            
    print("Semeadura concluida!")

if __name__ == "__main__":
    asyncio.run(seed_db())
