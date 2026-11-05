from django.conf import settings
from django.db import models


class TutorialVisto(models.Model):
    """Marca quem já passou pelo tutorial de boas-vindas (existir o registro = já viu)."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutorial_visto")
    visto_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tutorial visto"
        verbose_name_plural = "tutoriais vistos"

    def __str__(self):
        return f"{self.usuario} — {self.visto_em:%d/%m/%Y}"
