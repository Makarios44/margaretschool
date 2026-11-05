from django.conf import settings
from django.db import models

LOGINS_COM_FAIXA_DE_AJUDA = 5  # depois do 5º login a faixa de ajuda some do painel


class TutorialVisto(models.Model):
    """Acompanhamento do tutorial por usuário: quantos logins já fez e quando concluiu (ou pulou) o tutorial."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutorial_visto")
    visto_em = models.DateTimeField(null=True, blank=True)
    logins = models.PositiveIntegerField("Logins feitos", default=0)

    class Meta:
        verbose_name = "tutorial visto"
        verbose_name_plural = "tutoriais vistos"

    def __str__(self):
        return f"{self.usuario} — {self.logins} login(s)"

    @classmethod
    def visto_por(cls, usuario):
        return cls.objects.filter(usuario=usuario, visto_em__isnull=False).exists()

    @classmethod
    def mostrar_faixa(cls, usuario):
        """Faixa de ajuda no painel: aparece até o 5º login."""
        acompanhamento = cls.objects.filter(usuario=usuario).first()
        return acompanhamento is None or acompanhamento.logins <= LOGINS_COM_FAIXA_DE_AJUDA
