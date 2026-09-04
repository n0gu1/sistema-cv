import json
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from reclutamiento.email_backend import BrevoEmailBackend


class BrevoEmailBackendTests(SimpleTestCase):
    @override_settings(
        BREVO_API_KEY="test-api-key",
        BREVO_API_URL="https://api.brevo.test/v3/smtp/email",
        EMAIL_TIMEOUT=7,
    )
    @patch("reclutamiento.email_backend.urlopen")
    def test_sends_text_and_html_content_over_https(self, urlopen):
        response = MagicMock(status=201)
        response.__enter__.return_value = response
        urlopen.return_value = response
        message = EmailMultiAlternatives(
            subject="Verifica tu cuenta",
            body="Abre el enlace.",
            from_email="Sistema CV <sender@example.com>",
            to=["Elena Morales <elena@example.com>"],
            reply_to=["soporte@example.com"],
        )
        message.attach_alternative("<p>Abre el enlace.</p>", "text/html")

        sent = BrevoEmailBackend().send_messages([message])

        self.assertEqual(sent, 1)
        request = urlopen.call_args.args[0]
        timeout = urlopen.call_args.kwargs["timeout"]
        self.assertEqual(request.full_url, "https://api.brevo.test/v3/smtp/email")
        self.assertEqual(timeout, 7)
        self.assertEqual(
            {key.lower(): value for key, value in request.header_items()}["api-key"],
            "test-api-key",
        )
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["sender"], {"email": "sender@example.com", "name": "Sistema CV"})
        self.assertEqual(
            payload["to"],
            [{"email": "elena@example.com", "name": "Elena Morales"}],
        )
        self.assertEqual(payload["textContent"], "Abre el enlace.")
        self.assertEqual(payload["htmlContent"], "<p>Abre el enlace.</p>")
        self.assertEqual(payload["replyTo"], {"email": "soporte@example.com"})

    @override_settings(BREVO_API_KEY="")
    def test_requires_api_key(self):
        message = EmailMultiAlternatives(
            subject="Prueba",
            body="Contenido",
            from_email="sender@example.com",
            to=["recipient@example.com"],
        )

        with self.assertRaises(ImproperlyConfigured):
            BrevoEmailBackend().send_messages([message])
