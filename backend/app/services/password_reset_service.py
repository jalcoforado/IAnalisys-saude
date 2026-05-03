"""
Service de recuperação de senha.

Fluxo:
  1. `request_reset(email)` — gera token aleatório (32 bytes hex), armazena
     o SHA-256 do token, dispara email com link contendo o token raw.
     Sempre executa "sucesso silencioso" — não revela se o email existe.

  2. `confirm_reset(token, new_password)` — encontra registro pelo SHA-256
     do token, valida não-expirado e não-usado, troca a senha do usuário
     e marca o token como consumido. Lança PasswordResetError em qualquer
     falha.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.security.password import hash_password
from app.services.email_service import send_invite_email, send_password_reset_email

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(hours=1)
INVITE_TTL = timedelta(hours=72)
TOKEN_BYTES = 32  # 64 chars hex — entropia suficiente


class PasswordResetError(Exception):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def request_reset(db: AsyncSession, email: str, requested_ip: str | None = None) -> None:
    """
    Cria um token de reset e dispara email. Em qualquer falha (email não
    existe, usuário inativo, SMTP off) loga e retorna silenciosamente —
    o caller sempre responde 200 ao cliente para não revelar existência
    de conta.
    """
    q = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = q.scalar_one_or_none()

    if not user or not user.is_active:
        logger.info("Reset solicitado para email não cadastrado/inativo: %s", email)
        return

    raw_token = secrets.token_hex(TOKEN_BYTES)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + TOKEN_TTL

    record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        requested_ip=requested_ip,
    )
    db.add(record)
    await db.commit()

    reset_url = f"{settings.APP_URL.rstrip('/')}/auth/redefinir-senha?token={raw_token}"

    try:
        await send_password_reset_email(
            to_email=user.email,
            full_name=user.full_name,
            reset_url=reset_url,
        )
    except Exception:
        # Email falhou — token já foi criado, mas avisamos o log. Não
        # propagamos para não revelar nada ao cliente.
        logger.exception("Falha ao enviar email de reset, mas token criado para %s", user.email)


async def create_invite_token(
    db: AsyncSession,
    *,
    user: User,
    tenant_name: str,
) -> str:
    """
    Cria token de convite (purpose='invite', TTL 72h) e dispara email.
    Retorna o token raw (para testes/log). Caller faz commit fora se quiser
    transacionar — aqui já fazemos commit do token.
    """
    raw_token = secrets.token_hex(TOKEN_BYTES)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + INVITE_TTL

    record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        purpose="invite",
    )
    db.add(record)
    await db.commit()

    invite_url = f"{settings.APP_URL.rstrip('/')}/auth/redefinir-senha?token={raw_token}"

    try:
        await send_invite_email(
            to_email=user.email,
            full_name=user.full_name,
            tenant_name=tenant_name,
            invite_url=invite_url,
        )
    except Exception:
        logger.exception("Falha ao enviar convite para %s, token criado", user.email)

    return raw_token


async def confirm_reset(db: AsyncSession, token: str, new_password: str) -> User:
    """
    Valida token e troca a senha. Lança PasswordResetError com mensagem
    pública (sem detalhes internos) em caso de qualquer falha.
    """
    if len(new_password) < 8:
        raise PasswordResetError("A senha precisa de pelo menos 8 caracteres.")

    token_hash = _hash_token(token)
    q = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    record = q.scalar_one_or_none()

    if not record:
        raise PasswordResetError("Link inválido ou já utilizado.")
    if record.used_at is not None:
        raise PasswordResetError("Este link já foi utilizado.")
    # Comparação tz-aware: expires_at vem como datetime UTC
    now = datetime.now(timezone.utc)
    expires = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires < now:
        raise PasswordResetError("Link expirado. Solicite um novo.")

    user_q = await db.execute(select(User).where(User.id == record.user_id, User.deleted_at.is_(None)))
    user = user_q.scalar_one_or_none()
    if not user or not user.is_active:
        raise PasswordResetError("Conta não encontrada ou inativa.")

    user.hashed_password = hash_password(new_password)
    record.used_at = now
    await db.commit()
    await db.refresh(user)

    logger.info("Senha redefinida para usuário %s via token %s…", user.email, token_hash[:8])
    return user
