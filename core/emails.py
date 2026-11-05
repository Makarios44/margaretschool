"""Envio de e-mails da plataforma (link de senha, convites, teste)."""
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

log = logging.getLogger(__name__)


def enviar(assunto, texto, html, destinatarios):
    """Envia um e-mail de texto + HTML. Devolve True se o backend aceitou."""
    msg = EmailMultiAlternatives(assunto, texto, settings.DEFAULT_FROM_EMAIL, list(destinatarios))
    if html:
        msg.attach_alternative(html, "text/html")
    return msg.send() > 0


def link_de_senha(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return request.build_absolute_uri(reverse("password_reset_confirm", args=[uid, token]))


def enviar_link_senha(request, usuario, convite=False):
    """Manda ao usuário o link para (re)definir a senha. Devolve True/False; nunca levanta erro."""
    if not usuario.email:
        return False
    contexto = {
        "usuario": usuario, "link": link_de_senha(request, usuario),
        "escola": settings.ESCOLA["nome"], "convite": convite,
        "horas": settings.PASSWORD_RESET_TIMEOUT // 3600,
    }
    assunto = ("Seu acesso ao portal da %s" if convite else "Redefinição de senha – %s") % settings.ESCOLA["nome"]
    try:
        return enviar(assunto, render_to_string("registration/email_senha.txt", contexto),
                      render_to_string("registration/email_senha.html", contexto), [usuario.email])
    except Exception:  # falha de rede/chave inválida não pode derrubar a tela
        log.exception("Falha ao enviar e-mail de senha para o usuário %s", usuario.pk)
        return False
