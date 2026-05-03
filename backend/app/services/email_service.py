"""
Serviço de envio de email via SMTP (Gmail por enquanto).

Em desenvolvimento usa Gmail com app password (limite 500 emails/dia).
Em produção, migrar para Sendgrid/Resend/Mailgun — basta trocar
`SMTP_HOST` no .env, a interface do service não muda.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


def _password_reset_html(full_name: str, reset_url: str) -> str:
    """Template HTML inline simples — sem Jinja para evitar dependência."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#F5F5F5;margin:0;padding:24px;">
  <div style="max-width:520px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#1D4ED8 0%,#1E40AF 100%);padding:24px 32px;color:white;">
      <div style="font-size:18px;font-weight:bold;letter-spacing:-0.3px;">IAnalisys Saúde</div>
      <div style="font-size:11px;opacity:0.85;margin-top:2px;text-transform:uppercase;letter-spacing:1px;">Recuperação de senha</div>
    </div>
    <div style="padding:28px 32px;color:#262626;line-height:1.55;">
      <p style="margin:0 0 16px;">Olá, <strong>{full_name}</strong>!</p>
      <p style="margin:0 0 16px;">
        Recebemos uma solicitação para redefinir a senha da sua conta. Se foi você,
        clique no botão abaixo. Se não foi, ignore este email — sua senha continua segura.
      </p>
      <p style="text-align:center;margin:28px 0;">
        <a href="{reset_url}" style="display:inline-block;background:#1D4ED8;color:white;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px;">
          Redefinir minha senha
        </a>
      </p>
      <p style="margin:16px 0 0;font-size:12px;color:#737373;">
        Este link é válido por <strong>1 hora</strong> e pode ser usado uma única vez.
      </p>
      <p style="margin:8px 0 0;font-size:11px;color:#A3A3A3;word-break:break-all;">
        Se o botão não funcionar, copie e cole no navegador:<br/>
        <span style="color:#525252;">{reset_url}</span>
      </p>
    </div>
    <div style="padding:16px 32px;background:#FAFAFA;border-top:1px solid #E5E5E5;font-size:11px;color:#A3A3A3;text-align:center;">
      Este é um email automático. Não responda.
    </div>
  </div>
</body>
</html>
"""


def _password_reset_text(full_name: str, reset_url: str) -> str:
    """Fallback text/plain pra clientes sem HTML."""
    return (
        f"Olá, {full_name}!\n\n"
        f"Recebemos uma solicitação para redefinir a senha da sua conta IAnalisys Saúde.\n\n"
        f"Se foi você, acesse o link abaixo (válido por 1 hora, uso único):\n"
        f"{reset_url}\n\n"
        f"Se não foi você, ignore este email — sua senha continua segura.\n\n"
        f"— IAnalisys Saúde\n"
    )


def _invite_html(full_name: str, tenant_name: str, invite_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#F5F5F5;margin:0;padding:24px;">
  <div style="max-width:520px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:linear-gradient(135deg,#1D4ED8 0%,#1E40AF 100%);padding:24px 32px;color:white;">
      <div style="font-size:18px;font-weight:bold;letter-spacing:-0.3px;">IAnalisys Saúde</div>
      <div style="font-size:11px;opacity:0.85;margin-top:2px;text-transform:uppercase;letter-spacing:1px;">Você foi convidado</div>
    </div>
    <div style="padding:28px 32px;color:#262626;line-height:1.55;">
      <p style="margin:0 0 16px;">Olá, <strong>{full_name}</strong>!</p>
      <p style="margin:0 0 16px;">
        Você foi convidado(a) para acessar a plataforma <strong>IAnalisys Saúde</strong>
        em nome de <strong>{tenant_name}</strong>. Para começar, defina sua senha de acesso:
      </p>
      <p style="text-align:center;margin:28px 0;">
        <a href="{invite_url}" style="display:inline-block;background:#1D4ED8;color:white;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:14px;">
          Definir minha senha
        </a>
      </p>
      <p style="margin:16px 0 0;font-size:12px;color:#737373;">
        Este link é válido por <strong>72 horas</strong> e pode ser usado uma única vez.
      </p>
      <p style="margin:8px 0 0;font-size:11px;color:#A3A3A3;word-break:break-all;">
        Se o botão não funcionar, copie e cole no navegador:<br/>
        <span style="color:#525252;">{invite_url}</span>
      </p>
    </div>
    <div style="padding:16px 32px;background:#FAFAFA;border-top:1px solid #E5E5E5;font-size:11px;color:#A3A3A3;text-align:center;">
      Se você não esperava este convite, ignore este email.
    </div>
  </div>
</body>
</html>
"""


def _invite_text(full_name: str, tenant_name: str, invite_url: str) -> str:
    return (
        f"Olá, {full_name}!\n\n"
        f"Você foi convidado(a) para acessar a plataforma IAnalisys Saúde em nome de {tenant_name}.\n\n"
        f"Defina sua senha de acesso pelo link abaixo (válido por 72h, uso único):\n"
        f"{invite_url}\n\n"
        f"Se você não esperava este convite, ignore este email.\n\n"
        f"— IAnalisys Saúde\n"
    )


async def send_invite_email(*, to_email: str, full_name: str, tenant_name: str, invite_url: str) -> None:
    """Envia email de convite pra novo usuário definir sua senha inicial."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP não configurado — convite não enviado para %s", to_email)
        return

    msg = EmailMessage()
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL or settings.SMTP_USER))
    msg["To"] = to_email
    msg["Subject"] = f"Convite — IAnalisys Saúde ({tenant_name})"

    msg.set_content(_invite_text(full_name, tenant_name, invite_url))
    msg.add_alternative(_invite_html(full_name, tenant_name, invite_url), subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
            timeout=15,
        )
        logger.info("Convite enviado para %s", to_email)
    except Exception as exc:
        logger.exception("Falha ao enviar convite para %s: %s", to_email, exc)
        raise


async def send_password_reset_email(*, to_email: str, full_name: str, reset_url: str) -> None:
    """
    Envia email de recuperação de senha. Levanta exceção em falha — o caller
    decide se loga e suprime ou se propaga (no fluxo público nós sempre
    suprimimos para não vazar se o email existe).
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP não configurado (SMTP_USER/SMTP_PASSWORD vazios) — email não enviado.")
        return

    msg = EmailMessage()
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL or settings.SMTP_USER))
    msg["To"] = to_email
    msg["Subject"] = "Redefinir senha — IAnalisys Saúde"

    msg.set_content(_password_reset_text(full_name, reset_url))
    msg.add_alternative(_password_reset_html(full_name, reset_url), subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
            timeout=15,
        )
        logger.info("Email de reset enviado para %s", to_email)
    except Exception as exc:
        logger.exception("Falha ao enviar email de reset para %s: %s", to_email, exc)
        raise
