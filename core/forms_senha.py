from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache

from .emails import enviar_link_senha

User = get_user_model()
INTERVALO_SEGUNDOS = 60


class PedidoDeSenhaForm(PasswordResetForm):
    """Pede o e-mail; só envia para contas ativas com senha, no máximo 1 vez por minuto por e-mail.
    A resposta na tela é sempre a mesma, exista a conta ou não."""

    def save(self, request=None, **kwargs):
        email = self.cleaned_data["email"].strip().lower()
        chave = f"senha-pedido:{email}"
        if not cache.add(chave, 1, INTERVALO_SEGUNDOS):
            return
        for usuario in self.get_users(email):
            enviar_link_senha(request, usuario)
