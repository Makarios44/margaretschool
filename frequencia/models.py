from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from matriculas.models import Matricula, Turma


class Chamada(models.Model):
    """Chamada de uma turma em um dia. Cada chamada registrada conta como um dia de aula da turma."""

    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="chamadas")
    data = models.DateField("Data", db_index=True)
    observacao = models.CharField("Observação do dia", max_length=200, blank=True,
                                  help_text="Ex.: passeio, saída antecipada, chuva forte.")
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "turma__nome"]
        constraints = [models.UniqueConstraint(fields=["turma", "data"], name="uniq_chamada_turma_data")]
        verbose_name = "chamada"
        verbose_name_plural = "chamadas"

    def __str__(self):
        return f"{self.turma.nome} — {self.data:%d/%m/%Y}"


class Presenca(models.Model):
    """Situação de um aluno (matrícula) em uma chamada."""

    class Status(models.TextChoices):
        PRESENTE = "P", "Presente"
        FALTA = "F", "Falta"
        JUSTIFICADA = "J", "Falta justificada"

    chamada = models.ForeignKey(Chamada, on_delete=models.CASCADE, related_name="presencas")
    matricula = models.ForeignKey(Matricula, on_delete=models.CASCADE, related_name="presencas")
    status = models.CharField("Situação", max_length=1, choices=Status.choices, default=Status.PRESENTE)
    justificativa = models.CharField("Justificativa", max_length=200, blank=True,
                                     help_text="Ex.: atestado médico, viagem da família.")

    class Meta:
        ordering = ["matricula__aluno__nome"]
        constraints = [models.UniqueConstraint(fields=["chamada", "matricula"], name="uniq_presenca_chamada_matricula")]
        verbose_name = "presença"
        verbose_name_plural = "presenças"

    def __str__(self):
        return f"{self.matricula.aluno} — {self.chamada.data:%d/%m/%Y}: {self.get_status_display()}"

    @property
    def faltou(self):
        return self.status != self.Status.PRESENTE

    def clean(self):
        if self.status == self.Status.JUSTIFICADA and not self.justificativa.strip():
            raise ValidationError({"justificativa": "Informe a justificativa da falta."})
