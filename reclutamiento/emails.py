from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from reclutamiento.tokens import email_verification_token


def send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verification_url = request.build_absolute_uri(
        reverse(
            "verificar_correo",
            kwargs={"uidb64": uid, "token": token},
        )
    )
    context = {"user": user, "verification_url": verification_url}
    text_body = render_to_string("emails/verificar_correo.txt", context)
    html_body = render_to_string("emails/verificar_correo.html", context)
    message = EmailMultiAlternatives(
        subject="Verifica tu cuenta de Nexo Talento",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    return message.send()
