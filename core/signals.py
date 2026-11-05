from django.contrib.auth.signals import user_logged_in
from django.db.models import F
from django.dispatch import receiver

from .models import TutorialVisto


@receiver(user_logged_in)
def contar_login(sender, request, user, **kwargs):
    """Conta cada login da pessoa (usado para esconder a faixa de ajuda depois do 5º)."""
    TutorialVisto.objects.get_or_create(usuario=user)
    TutorialVisto.objects.filter(usuario=user).update(logins=F("logins") + 1)
