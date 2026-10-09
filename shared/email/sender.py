"""Simple async email sender using stdlib smtplib."""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


async def send_verification_email(to_email: str, verify_url: str) -> bool:
    """Send email verification link asynchronously. Returns True on success."""
    try:
        from shared.config import settings

        if not settings.email_enabled or not settings.smtp_host:
            logger.info("Email not enabled — skip sending to %s", to_email)
            return False

        subject = "Verify your TopInjector account"
        body = f"""Please verify your email by clicking the link below:

{verify_url}

If you did not register, ignore this email.
"""
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_email

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _send_sync,
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_from,
            to_email,
            msg.as_string(),
        )
        logger.info("Verification email sent to %s", to_email)
        return True

    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
        return False


def _send_sync(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_addr: str,
    message: str,
) -> None:
    """Synchronous SMTP send (runs in executor)."""
    with smtplib.SMTP(host, port, timeout=10) as server:
        server.ehlo()
        if port == 465:
            # SSL mode
            server.login(user, password)
        else:
            server.starttls()
            server.ehlo()
            server.login(user, password)
        server.sendmail(from_addr, to_addr, message)
