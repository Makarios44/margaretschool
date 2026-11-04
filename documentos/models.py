from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Max

from alunos.models import Aluno
from matriculas.models import Matricula

from . import regras


class RegistroEscolar(models.Model):
    """Dados escolares de uma matrícula (frequência, resultado e parecer do ano)."""

    class Resultado(models.TextChoices):
        EM_CURSO = "em_curso", "Em curso"
        CONCLUIDO = "concluido", "Concluído"
        APROVADO = "aprovado", "Aprovado(a)"
        RETIDO = "retido", "Retido(a)"
        TRANSFERIDO = "transferido", "Transferido(a)"

    matricula = models.OneToOneField(Matricula, on_delete=models.CASCADE, related_name="registro")
    carga_horaria = models.PositiveSmallIntegerField("Carga horária anual (horas)", null=True, blank=True)
    dias_letivos = models.PositiveSmallIntegerField("Dias letivos", null=True, blank=True)
    faltas = models.PositiveSmallIntegerField("Faltas", null=True, blank=True)
    resultado = models.CharField(
        "Resultado", max_length=12, choices=Resultado.choices, default=Resultado.EM_CURSO
    )
    parecer = models.TextField(
        "Parecer descritivo / observações", blank=True,
        help_text="Na educação infantil, descreva o desenvolvimento e as aprendizagens da criança.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "registro escolar"
        verbose_name_plural = "registros escolares"

    def __str__(self):
        return f"Registro — {self.matricula}"

    @property
    def frequencia(self):
        """Percentual de presença no ano (1 casa decimal) ou None se faltar dado."""
        if not self.dias_letivos or self.faltas is None:
            return None
        pct = Decimal(self.dias_letivos - self.faltas) / Decimal(self.dias_letivos) * 100
        return pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    def clean(self):
        erros = {}
        if self.dias_letivos is not None and self.faltas is not None and self.faltas > self.dias_letivos:
            erros["faltas"] = "As faltas não podem ser maiores que os dias letivos."
        if self.matricula_id and regras.eh_infantil(self.matricula.etapa) and self.resultado in (
            self.Resultado.APROVADO, self.Resultado.RETIDO,
        ):
            erros["resultado"] = (
                "Na educação infantil não há aprovação nem retenção (LDB, art. 31, I). "
                "Use \"Concluído\" ou \"Em curso\"."
            )
        if erros:
            raise ValidationError(erros)


class ComponenteRegistro(models.Model):
    """Componente curricular e resultado final (ensino fundamental)."""

    registro = models.ForeignKey(RegistroEscolar, on_delete=models.CASCADE, related_name="componentes")
    nome = models.CharField("Componente curricular", max_length=80)
    carga_horaria = models.PositiveSmallIntegerField("Carga horária (h)", null=True, blank=True)
    resultado = models.CharField("Resultado final (nota ou conceito)", max_length=30, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nome


class DocumentoEmitido(models.Model):
    """Livro de registro dos documentos expedidos.

    O conteúdo é guardado como foto do momento (`conteudo`): se o cadastro mudar depois,
    a segunda via continua igual ao que foi emitido.
    """

    class Tipo(models.TextChoices):
        DECLARACAO_MATRICULA = "declaracao_matricula", "Declaração de matrícula"
        DECLARACAO_FREQUENCIA = "declaracao_frequencia", "Declaração de frequência"
        HISTORICO = "historico", "Histórico / ficha de registros escolares"
        TRANSFERENCIA = "transferencia", "Documento de transferência"

    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="documentos_emitidos")
    matricula = models.ForeignKey(
        Matricula, on_delete=models.PROTECT, null=True, blank=True, related_name="documentos_emitidos"
    )
    ano = models.PositiveSmallIntegerField()
    sequencial = models.PositiveIntegerField()
    emitido_em = models.DateTimeField(auto_now_add=True)
    emitido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    conteudo = models.JSONField()
    anulado = models.BooleanField(default=False)
    anulado_em = models.DateTimeField(null=True, blank=True)
    anulado_motivo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-ano", "-sequencial"]
        unique_together = [("ano", "sequencial")]
        verbose_name = "documento emitido"
        verbose_name_plural = "documentos emitidos"

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero} — {self.aluno}"

    @property
    def numero(self):
        return f"{self.ano}/{self.sequencial:04d}"

    @classmethod
    def emitir(cls, tipo, aluno, conteudo, usuario=None, matricula=None):
        """Cria o documento com o próximo número do ano (tenta de novo se houver corrida)."""
        ano = date.today().year
        for _ in range(5):
            ultimo = cls.objects.filter(ano=ano).aggregate(m=Max("sequencial"))["m"] or 0
            try:
                with transaction.atomic():
                    return cls.objects.create(
                        tipo=tipo, aluno=aluno, matricula=matricula, ano=ano, sequencial=ultimo + 1,
                        conteudo=conteudo, emitido_por=usuario,
                    )
            except IntegrityError:
                continue
        raise RuntimeError("Não foi possível reservar o número do documento. Tente novamente.")
