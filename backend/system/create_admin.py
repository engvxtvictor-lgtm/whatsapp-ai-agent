"""
Script CLI para criar ou atualizar um administrador no banco de dados.

Uso:
    python -m backend.system.create_admin --email admin@lumina.com --password SenhaForte123 --name "Dr. Admin" --role Administrador

Requisitos:
    - DATABASE_URL configurado no .env ou como variável de ambiente
    - Banco de dados já inicializado (docker-compose up)
"""
import asyncio
import argparse
import sys

from sqlalchemy import select

from backend.system.database import AsyncSession, create_tables
from backend.system.models.web_models import AdminWeb
from backend.system.auth import get_password_hash


async def create_or_update_admin(email: str, password: str, name: str, role: str) -> None:
    await create_tables()

    async with AsyncSession() as session:
        result = await session.execute(
            select(AdminWeb).where(AdminWeb.email == email)
        )
        existing = result.scalars().first()

        if existing:
            existing.password_hash = get_password_hash(password)
            existing.name = name
            existing.role = role
            await session.commit()
            print(f"✅ Admin '{email}' atualizado com sucesso.")
        else:
            new_admin = AdminWeb(
                name=name,
                email=email,
                role=role,
                password_hash=get_password_hash(password),
                avatar=f"https://api.dicebear.com/7.x/avataaars/svg?seed={name}",
            )
            session.add(new_admin)
            await session.commit()
            print(f"✅ Admin '{email}' criado com sucesso.")


def main():
    parser = argparse.ArgumentParser(description="Criar ou atualizar administrador no banco de dados.")
    parser.add_argument("--email", required=True, help="E-mail do administrador")
    parser.add_argument("--password", required=True, help="Senha do administrador")
    parser.add_argument("--name", default="Administrador", help="Nome completo")
    parser.add_argument("--role", default="Administrador", help="Cargo/função")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ Erro: A senha deve ter pelo menos 8 caracteres.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(create_or_update_admin(args.email, args.password, args.name, args.role))


if __name__ == "__main__":
    main()
