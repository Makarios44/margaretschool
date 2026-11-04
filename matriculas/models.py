from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from alunos.models import Aluno


class Turno(models.TextChoices):
    MANHA = "manha", "Manhã"
    TARDE = "tarde", "Tarde"
    INTEGRAL = "integral", "Integral"


class Etapa(models.TextChoices):
    """Etapa de ensino da turma. Define o modelo dos documentos escolares."""

    INFANTIL_CRECHE = "infantil_creche", "Educação Infantil — Creche"
    INFANTIL_PRE = "infantil_pre", "Educação Infantil — Pré-escola"
    FUNDAMENTAL_INICIAIS = "fundamental_iniciais", "Ensino Fundamental — anos iniciais"


class AnoLetivo(models.Model):
    ano = models.PositiveSmallIntegerField("Ano", unique=True)
    atual = models.BooleanField(
        "Ano atual", default=False,
        help_text="Usado como padrão nas telas. Só um ano pode ser o atual.",
    )
    inicio_aulas = models.DateField("Início das aulas", null=True, blank=True)
    fim_aulas = models.DateField("Fim das aulas", null=True, blank=True)
    horas_dia_letivo = models.DecimalField(
        "Horas de trabalho escolar por dia letivo", max_digits=3, decimal_places=1, default=4,
        help_text="Em horas de 60 minutos. 4 h/dia × 200 dias = 800 h (mínimo legal).",
    )

    class Meta:
        ordering = ["-ano"]
        verbose_name = "ano letivo"
        verbose_name_plural = "anos letivos"

    def __str__(self):
        return str(self.ano)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.atual:
            AnoLetivo.objects.exclude(pk=self.pk).update(atual=False)

    @classmethod
    def padrao(cls):
        """Ano marcado como atual; se não houver, o mais recente."""
        return cls.objects.filter(atual=True).first() or cls.objects.first()


class Turma(models.Model):
    nome = models.CharField("Nome da turma", max_length=60, help_text="Ex.: Maternal II")
    ano_letivo = models.ForeignKey(
        AnoLetivo, on_delete=models.PROTECT, related_name="turmas"
    )
    turno = models.CharField("Turno", max_length=10, choices=Turno.choices)
    etapa = models.CharField(
        "Etapa de ensino", max_length=25, choices=Etapa.choices, default=Etapa.INFANTIL_PRE,
        help_text="Define o modelo dos documentos escolares (frequência, histórico, transferência). "
                  "Confira a etapa de cada turma.",
    )
    vagas = models.PositiveSmallIntegerField("Vagas", null=True, blank=True)

    class Meta:
        ordering = ["-ano_letivo__ano", "nome", "turno"]
        unique_together = [("nome", "ano_letivo", "turno")]

    def __str__(self):
        return f"{self.nome} · {self.get_turno_display()} ({self.ano_letivo})"

    @property
    def ocupacao(self):
        return self.matriculas.filter(situacao=Matricula.Situacao.ATIVO).count()


class Matricula(models.Model):
    class Situacao(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        TRANSFERIDO = "transferido", "Transferido"
        CANCELADO = "cancelado", "Cancelado"
        CONCLUIDO = "concluido", "Concluído"

    class Tipo(models.TextChoices):
        NOVA = "nova", "Matrícula nova"
        REMATRICULA = "rematricula", "Rematrícula"

    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name="matriculas")
    ano_letivo = models.ForeignKey(
        AnoLetivo, on_delete=models.PROTECT, related_name="matriculas"
    )
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="matriculas")
    turno = models.CharField(max_length=10, choices=Turno.choices, editable=False)
    tipo = models.CharField("Tipo", max_length=12, choices=Tipo.choices, default=Tipo.NOVA)
    data_matricula = models.DateField("Data da matrícula", default=date.today)
    situacao = models.CharField(
        "Situação", max_length=12, choices=Situacao.choices, default=Situacao.ATIVO
    )
    taxa_matricula = models.DecimalField(
        "Taxa de matrícula (R$)", max_digits=8, decimal_places=2, default=0
    )
    taxa_paga = models.BooleanField("Taxa de matrícula paga", default=False)
    mensalidade = models.DecimalField("Mensalidade (R$)", max_digits=8, decimal_places=2)
    dia_vencimento = models.PositiveSmallIntegerField(
        "Dia de vencimento", default=10,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    desconto_percentual = models.DecimalField(
        "Bolsa / desconto na mensalidade (%)", max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Vale para as mensalidades geradas daqui em diante.",
    )
    desconto_motivo = models.CharField(
        "Motivo da bolsa / desconto", max_length=100, blank=True,
        help_text="Ex.: irmão na escola, bolsa integral, convênio",
    )
    observacoes = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ano_letivo__ano", "-data_matricula", "-id"]
        unique_together = [("aluno", "ano_letivo")]
        verbose_name = "matrícula"
        verbose_name_plural = "matrículas"

    def __str__(self):
        return f"{self.aluno} — {self.ano_letivo}"

    @property
    def etapa(self):
        return self.turma.etapa

    @property
    def desconto_valor(self):
        """Desconto em reais aplicado a cada mensalidade."""
        return (self.mensalidade * self.desconto_percentual / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def mensalidade_liquida(self):
        return self.mensalidade - self.desconto_valor

    @property
    def desconto_descricao(self):
        return self.desconto_motivo or f"Desconto de {self.desconto_percentual:.0f}%"

    @property
    def situacao_css(self):
        return f"sit-{self.situacao}"

    def clean(self):
        if self.turma_id and self.ano_letivo_id and self.turma.ano_letivo_id != self.ano_letivo_id:
            raise ValidationError(
                {"turma": "Esta turma pertence a outro ano letivo. Escolha uma turma de "
                          f"{self.ano_letivo}."}
            )

    def save(self, *args, **kwargs):
        self.turno = self.turma.turno  # o turno vem sempre da turma escolhida
        criando = self.pk is None
        super().save(*args, **kwargs)
        if criando:
            DocumentoMatricula.objects.bulk_create(
                DocumentoMatricula(matricula=self, tipo=t)
                for t in DocumentoMatricula.OBRIGATORIOS
            )

    @property
    def docs_pendentes(self):
        return self.documentos.filter(entregue=False).count()


class DocumentoMatricula(models.Model):
    class Tipo(models.TextChoices):
        CERTIDAO = "certidao", "Certidão de nascimento da criança"
        VACINA = "vacina", "Cartão de vacinação"
        DOC_RESP = "doc_resp", "Documento com foto e CPF do responsável"
        RESIDENCIA = "residencia", "Comprovante de residência"
        FOTO = "foto", "Foto 3x4 da criança"
        TRANSFERENCIA = "transferencia", "Declaração de transferência"
        LAUDO = "laudo", "Laudo ou relatório médico"

    # Criados automaticamente (como pendentes) em toda matrícula.
    # Os demais tipos são adicionados na tela da matrícula, quando necessários.
    OBRIGATORIOS = [Tipo.CERTIDAO, Tipo.VACINA, Tipo.DOC_RESP, Tipo.RESIDENCIA, Tipo.FOTO]

    matricula = models.ForeignKey(
        Matricula, on_delete=models.CASCADE, related_name="documentos"
    )
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    entregue = models.BooleanField(default=False)
    data_entrega = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        unique_together = [("matricula", "tipo")]
        verbose_name = "documento"
        verbose_name_plural = "documentos"

    def __str__(self):
        return self.get_tipo_display()
