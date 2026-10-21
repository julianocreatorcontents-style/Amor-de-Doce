"""Envio opcional do formulário de contato por e-mail (SMTP). Sem SMTP configurado, nada é enviado."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)


def smtp_configured() -> bool:
    c = current_app.config
    return bool(c["SMTP_HOST"] and c["CONTACT_EMAIL_TO"] and (c["SMTP_FROM"] or c["SMTP_USERNAME"]))


def send_contact_email(name: str, email: str, subject: str, body: str) -> str:
    """Retorna 'enviado', 'falhou' ou 'nao_configurado'."""
    if not smtp_configured():
        return "nao_configurado"
    c = current_app.config
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Site KNAZH] {subject}"
        msg["From"] = c["SMTP_FROM"] or c["SMTP_USERNAME"]
        msg["To"] = c["CONTACT_EMAIL_TO"]
        msg["Reply-To"] = email
        msg.set_content(f"Nome: {name}\nE-mail: {email}\nAssunto: {subject}\n\n{body}")
        with smtplib.SMTP(c["SMTP_HOST"], c["SMTP_PORT"], timeout=10) as smtp:
            if c["SMTP_USE_TLS"]:
                smtp.starttls()
            if c["SMTP_USERNAME"]:
                smtp.login(c["SMTP_USERNAME"], c["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return "enviado"
    except Exception:  # noqa: BLE001 - não expor detalhes ao visitante
        log.exception("Falha ao enviar e-mail de contato")
        return "falhou"
