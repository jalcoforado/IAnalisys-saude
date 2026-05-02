"""
Seed de desenvolvimento — cria tenant e usuário admin para testes.
Uso: docker compose run --rm backend python scripts/seed_dev.py
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.user_tenant import UserTenant
from app.security.password import hash_password

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

TENANT_ID = "00000000-0000-0000-0000-000000000001"
USER_ID    = "00000000-0000-0000-0000-000000000002"


async def seed():
    async with SessionLocal() as db:
        # Tenant
        existing = await db.get(Tenant, TENANT_ID)
        if not existing:
            tenant = Tenant(
                id=TENANT_ID,
                name="Parente Odontologia",
                slug="parente",
            )
            db.add(tenant)
            print(f"✓ Tenant criado: {tenant.name} (id={TENANT_ID})")
        else:
            print(f"→ Tenant já existe: {existing.name}")

        # Role tenant_admin
        role_result = await db.execute(
            select(Role).where(Role.name == "tenant_admin")
        )
        role = role_result.scalar_one_or_none()
        if not role:
            print("✗ Role 'tenant_admin' não encontrada. Rode as migrations primeiro.")
            return

        # User
        existing_user = await db.get(User, USER_ID)
        if not existing_user:
            user = User(
                id=USER_ID,
                email="admin@parente.com",
                full_name="Admin Parente",
                hashed_password=hash_password("admin123"),
                is_active=True,
                is_saas_admin=False,
            )
            db.add(user)
            print(f"✓ Usuário criado: {user.email} / senha: admin123")
        else:
            print(f"→ Usuário já existe: {existing_user.email}")
            user = existing_user

        await db.flush()

        # UserTenant
        ut_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == USER_ID,
                UserTenant.tenant_id == TENANT_ID,
            )
        )
        if not ut_result.scalar_one_or_none():
            db.add(UserTenant(
                id=str(uuid.uuid4()),
                user_id=USER_ID,
                tenant_id=TENANT_ID,
                role_id=role.id,
                is_active=True,
            ))
            print(f"✓ Vínculo user↔tenant criado com papel: {role.name}")

        await db.commit()

    print("\n=== Dados para teste ===")
    print(f"  tenant_id : {TENANT_ID}")
    print(f"  email     : admin@parente.com")
    print(f"  password  : admin123")
    print(f"  endpoint  : POST /api/v1/auth/login")


asyncio.run(seed())
