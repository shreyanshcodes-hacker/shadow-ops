from typing import Optional, Dict, Any, NamedTuple, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> EmailResult:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider implementation."""

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_USE_TLS
        self.from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        self.from_name = settings.SMTP_FROM_NAME or "ShadowOps Security"

    def is_configured(self) -> bool:
        return all([self.host, self.port, self.username, self.password, self.from_email])

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> EmailResult:
        if not self.is_configured():
            return EmailResult(
                success=False,
                error="SMTP not configured",
            )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{from_name or self.from_name} <{from_email or self.from_email}>"
            msg["To"] = to_email

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send via SMTP
            if self.use_tls:
                server = smtplib.SMTP(self.host, self.port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.host, self.port)

            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()

            return EmailResult(
                success=True,
                message_id=f"<{uuid.uuid4()}@shadowops>",
                provider_response={"provider": "smtp"},
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return EmailResult(success=False, error="SMTP authentication failed")
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipient refused: {e}")
            return EmailResult(success=False, error="Recipient refused")
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected: {e}")
            return EmailResult(success=False, error="SMTP server disconnected")
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return EmailResult(success=False, error=f"SMTP error: {str(e)}")


class SendGridEmailProvider(EmailProvider):
    """SendGrid email provider implementation."""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.from_name = settings.SENDGRID_FROM_NAME or "ShadowOps Security"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.from_email)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> EmailResult:
        if not self.is_configured():
            return EmailResult(
                success=False,
                error="SendGrid not configured",
            )

        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)

            mail = Mail(
                from_email=Email(from_email or self.from_email, from_name or self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_body),
                html_content=Content("text/html", html_body),
            )

            response = sg.client.mail.send.post(request_body=mail.get())

            return EmailResult(
                success=response.status_code in (200, 201, 202),
                message_id=response.headers.get("X-Message-Id"),
                provider_response={
                    "status_code": response.status_code,
                    "body": response.body,
                    "headers": dict(response.headers),
                },
            )

        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return EmailResult(success=False, error=f"SendGrid error: {str(e)}")


class ResendEmailProvider(EmailProvider):
    """Resend email provider implementation."""

    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.from_email = settings.RESEND_FROM_EMAIL
        self.from_name = settings.RESEND_FROM_NAME or "ShadowOps Security"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.from_email)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> EmailResult:
        if not self.is_configured():
            return EmailResult(
                success=False,
                error="Resend not configured",
            )

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": f"{from_name or self.from_name} <{from_email or self.from_email}>",
                        "to": [to_email],
                        "subject": subject,
                        "html": html_body,
                        "text": text_body,
                    },
                    timeout=30.0,
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    return EmailResult(
                        success=True,
                        message_id=data.get("id"),
                        provider_response=data,
                    )
                else:
                    return EmailResult(
                        success=False,
                        error=f"Resend API error: {response.status_code} - {response.text}",
                    )

        except Exception as e:
            logger.error(f"Resend error: {e}")
            return EmailResult(success=False, error=f"Resend error: {str(e)}")


class EmailAdapter:
    """Email adapter that selects the appropriate provider based on configuration."""

    def __init__(self):
        self.providers = []
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize providers in priority order."""
        # Try Resend first (modern, good deliverability)
        resend = ResendEmailProvider()
        if resend.is_configured():
            self.providers.append(resend)
            logger.info("Resend email provider configured")

        # Try SendGrid
        sendgrid = SendGridEmailProvider()
        if sendgrid.is_configured():
            self.providers.append(sendgrid)
            logger.info("SendGrid email provider configured")

        # Try SMTP as fallback
        smtp = SMTPEmailProvider()
        if smtp.is_configured():
            self.providers.append(smtp)
            logger.info("SMTP email provider configured")

        if not self.providers:
            logger.warning("No email providers configured. Email notifications will not work.")

    def is_configured(self) -> bool:
        return len(self.providers) > 0

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> 'EmailResult':
        """Send email using the first available provider."""
        if not self.providers:
            return EmailResult(
                success=False,
                error="No email providers configured",
            )

        last_error = None
        for provider in self.providers:
            try:
                result = await provider.send_email(
                    to_email=to_email,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                    from_email=from_email,
                    from_name=from_name,
                )
                if result.success:
                    logger.info(f"Email sent successfully via {provider.__class__.__name__}")
                    return result
                else:
                    last_error = result.error
                    logger.warning(f"Provider {provider.__class__.__name__} failed: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Provider {provider.__class__.__name__} exception: {e}")

        return EmailResult(
            success=False,
            error=f"All providers failed. Last error: {last_error}",
        )

    def get_provider_names(self) -> List[str]:
        """Get names of configured providers."""
        return [p.__class__.__name__ for p in self.providers]