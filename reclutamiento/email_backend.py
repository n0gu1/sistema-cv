import base64
import json
import logging
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)


class BrevoEmailError(RuntimeError):
    """Raised when Brevo rejects or cannot receive an email."""


class BrevoEmailBackend(BaseEmailBackend):
    api_url = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent = 0
        for email_message in email_messages:
            if not email_message.recipients():
                continue
            try:
                self._send_message(email_message)
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("No se pudo enviar un correo mediante Brevo")
            else:
                sent += 1
        return sent

    def _send_message(self, email_message):
        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not api_key:
            raise ImproperlyConfigured(
                "BREVO_API_KEY es obligatorio para usar el backend de Brevo."
            )

        sender = self._address(email_message.from_email)
        if not sender["email"]:
            raise ImproperlyConfigured(
                "DEFAULT_FROM_EMAIL debe contener una dirección válida."
            )

        payload = {
            "sender": sender,
            "to": [self._address(address) for address in email_message.to],
            "subject": email_message.subject,
        }
        if email_message.body:
            payload["textContent"] = email_message.body

        html_body = self._html_alternative(email_message)
        if html_body is not None:
            payload["htmlContent"] = html_body
        if "textContent" not in payload and "htmlContent" not in payload:
            payload["textContent"] = ""

        if email_message.cc:
            payload["cc"] = [self._address(address) for address in email_message.cc]
        if email_message.bcc:
            payload["bcc"] = [
                self._address(address) for address in email_message.bcc
            ]
        if email_message.reply_to:
            payload["replyTo"] = self._address(email_message.reply_to[0])
        if email_message.attachments:
            payload["attachment"] = [
                self._attachment(attachment)
                for attachment in email_message.attachments
            ]
        if email_message.extra_headers:
            payload["headers"] = {
                str(key): str(value)
                for key, value in email_message.extra_headers.items()
            }

        request = Request(
            getattr(settings, "BREVO_API_URL", self.api_url),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=getattr(settings, "EMAIL_TIMEOUT", 20)) as response:
                status = getattr(response, "status", 200)
                if not 200 <= status < 300:
                    raise BrevoEmailError(
                        f"Brevo respondió con el estado HTTP {status}."
                    )
        except HTTPError as error:
            raise BrevoEmailError(
                f"Brevo rechazó el correo con el estado HTTP {error.code}."
            ) from error
        except URLError as error:
            raise BrevoEmailError("No se pudo conectar con la API de Brevo.") from error

    @staticmethod
    def _address(address):
        name, email = parseaddr(str(address or ""))
        result = {"email": email or str(address or "").strip()}
        if name:
            result["name"] = name
        return result

    @staticmethod
    def _html_alternative(email_message):
        for alternative in getattr(email_message, "alternatives", ()):
            if hasattr(alternative, "content"):
                content = alternative.content
                mimetype = alternative.mimetype
            else:
                content, mimetype = alternative
            if mimetype == "text/html":
                return content
        return None

    @staticmethod
    def _attachment(attachment):
        if hasattr(attachment, "filename"):
            filename = attachment.filename
            content = attachment.content
        else:
            filename, content, _mimetype = attachment
        if isinstance(content, str):
            content = content.encode("utf-8")
        return {
            "name": filename,
            "content": base64.b64encode(content).decode("ascii"),
        }
