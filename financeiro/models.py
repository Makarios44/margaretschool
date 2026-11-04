from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from administracao import configuracao
from django.conf import settings as dj_settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q

from matriculas.models import Matricula

CENTAVO = Decimal("0.01")


def arredondar(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


# valor cobrado depois de descontos (usado em somas no banco)
LIQUIDO = ExpressionWrapper(
    F("valor") - F("desconto"), output_field=DecimalField(max_digits=10, decimal_places=2)
)


class Cobranca(models.Model):
    """Uma cobrança a receber de uma matrícula (mensalidade, taxa ou outra)."""

    class Tipo(models.TextChoices):
        MENSALIDADE = "mensalidade", "Mensalidade"
        TAXA_MATRICULA = "taxa_matricula", "Taxa de matrícula"
        AVULSA = "avulsa", "Outra cobrança"

    class Situacao(models.TextChoices):
        ABERTA = "aberta", "Em aberto"
        PAGA = "paga", "Paga"
        CANCELADA = "cancelada", "Cancelada"

    class Forma(models.TextChoices):
        PIX = "pix", "Pix"
        DINHEIRO = "dinheiro", "Dinheiro"
        CARTAO = "cartao", "Cartão"
        TRANSFERENCIA = "transferencia", "Transferência"

    STATUS_LABELS = {
        "pendente": "Pendente", "vencida": "Vencida", "paga": "Paga", "cancelada": "Cancelada",
    }

    matricula = models.ForeignKey(Matricula, on_delete=models.PROTECT, related_name="cobrancas")
    tipo = models.CharField("Tipo", max_length=15, choices=Tipo.choices, default=Tipo.MENSALIDADE)
    descricao = models.CharField("Descrição", max_length=120)
    competencia = models.DateField(null=True, blank=True, editable=False)  # 1º dia do mês
    vencimento = models.DateField("Vencimento")
    valor = models.DecimalField("Valor (R$)", max_digits=8, decimal_places=2)
    desconto = models.DecimalField("Desconto / abatimento (R$)", max_digits=8, decimal_places=2, default=0)
    motivo_desconto = models.CharField("Motivo do desconto", max_length=100, blank=True)
    situacao = models.CharField(max_length=10, choices=Situacao.choices, default=Situacao.ABERTA)

    # preenchidos ao receber
    data_pagamento = models.DateField("Data do pagamento", null=True, blank=True)
    forma_pagamento = models.CharField("Forma de pagamento", max_length=15, choices=Forma.choices, blank=True)
    multa = models.DecimalField("Multa (R$)", max_digits=8, decimal_places=2, default=0)
    juros = models.DecimalField("Juros (R$)", max_digits=8, decimal_places=2, default=0)
    valor_pago = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)

    observacoes = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vencimento", "id"]
        verbose_name = "cobrança"
        verbose_name_plural = "cobranças"
        constraints = [
            models.UniqueConstraint(
                fields=["matricula", "competencia"],
                condition=Q(tipo="mensalidade") & ~Q(situacao="cancelada"),
                name="uniq_mensalidade_por_mes",
            )
        ]

    def __str__(self):
        return f"{self.descricao} — {self.matricula.aluno}"

    # ---------- validação ----------
    def clean(self):
        erros = {}
        if self.valor is not None and self.desconto is not None and self.desconto > self.valor:
            erros["desconto"] = "O desconto não pode ser maior que o valor da cobrança."
        if self.tipo == self.Tipo.MENSALIDADE and self.vencimento:
            self.competencia = self.competencia or self.vencimento.replace(day=1)
            repetida = Cobranca.objects.filter(
                matricula_id=self.matricula_id, tipo=self.Tipo.MENSALIDADE,
                competencia=self.competencia,
            ).exclude(situacao=self.Situacao.CANCELADA).exclude(pk=self.pk)
            if self.matricula_id and repetida.exists():
                erros["vencimento"] = "Já existe mensalidade deste mês para esta matrícula."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        if self.tipo == self.Tipo.MENSALIDADE and not self.competencia and self.vencimento:
            self.competencia = self.vencimento.replace(day=1)
        super().save(*args, **kwargs)

    # ---------- valores ----------
    @property
    def valor_liquido(self):
        return max(self.valor - self.desconto, Decimal("0"))

    def dias_atraso(self, ref=None):
        ref = ref or date.today()
        return max((ref - self.vencimento).days, 0)

    def calcular_encargos(self, ref=None):
        """Multa e juros se a cobrança fosse paga em `ref` (padrão: hoje).

        Multa: percentual único sobre o valor. Juros: percentual ao mês,
        proporcional aos dias de atraso (mês de 30 dias).
        """
        dias = self.dias_atraso(ref)
        if dias == 0:
            return Decimal("0.00"), Decimal("0.00")
        cfg = configuracao.financeiro()
        base = self.valor_liquido
        multa = arredondar(base * cfg["multa_percentual"] / 100)
        juros = arredondar(base * cfg["juros_mensal_percentual"] / 100 / 30 * dias)
        return multa, juros

    @property
    def valor_atualizado(self):
        """Quanto cobrar hoje (com multa e juros). Para cobranças pagas, o valor pago."""
        if self.situacao == self.Situacao.PAGA:
            return self.valor_pago
        multa, juros = self.calcular_encargos()
        return self.valor_liquido + multa + juros

    # ---------- situação ----------
    @property
    def status(self):
        if self.situacao == self.Situacao.PAGA:
            return "paga"
        if self.situacao == self.Situacao.CANCELADA:
            return "cancelada"
        return "vencida" if self.vencimento < date.today() else "pendente"

    @property
    def status_display(self):
        return self.STATUS_LABELS[self.status]

    @property
    def status_css(self):
        return f"fin-{self.status}"

    @property
    def aberta(self):
        return self.situacao == self.Situacao.ABERTA

    @property
    def paga(self):
        return self.situacao == self.Situacao.PAGA

    @property
    def recibo_numero(self):
        return f"{self.data_pagamento.year}/{self.pk:05d}" if self.paga else ""

    # ---------- operações ----------
    @transaction.atomic
    def registrar_pagamento(self, data, forma, desconto=None, multa=None, juros=None, observacoes=None):
        if not self.aberta:
            raise ValueError("Só é possível receber cobranças em aberto.")
        if desconto is not None:
            self.desconto = desconto
        auto_multa, auto_juros = self.calcular_encargos(data)
        self.multa = auto_multa if multa is None else multa
        self.juros = auto_juros if juros is None else juros
        self.data_pagamento = data
        self.forma_pagamento = forma
        self.situacao = self.Situacao.PAGA
        self.valor_pago = self.valor_liquido + self.multa + self.juros
        if observacoes:
            self.observacoes = observacoes
        self.save()
        if self.tipo == self.Tipo.TAXA_MATRICULA:
            Matricula.objects.filter(pk=self.matricula_id).update(taxa_paga=True)

    @transaction.atomic
    def estornar(self):
        if not self.paga:
            raise ValueError("Só é possível estornar cobranças pagas.")
        self.situacao = self.Situacao.ABERTA
        self.data_pagamento = None
        self.forma_pagamento = ""
        self.multa = self.juros = Decimal("0.00")
        self.valor_pago = None
        self.save()
        if self.tipo == self.Tipo.TAXA_MATRICULA:
            Matricula.objects.filter(pk=self.matricula_id).update(taxa_paga=False)

    def cancelar(self):
        if not self.aberta:
            raise ValueError("Só é possível cancelar cobranças em aberto.")
        self.situacao = self.Situacao.CANCELADA
        self.save()


class CategoriaDespesa(models.Model):
    """Grupo de gastos (material, aluguel, salários…). Editável na Administração."""

    nome = models.CharField("Nome", max_length=60, unique=True)
    ativa = models.BooleanField("Ativa", default=True, help_text="Categorias desativadas não aparecem ao lançar despesas novas.")

    class Meta:
        ordering = ["nome"]
        verbose_name = "categoria de despesa"
        verbose_name_plural = "categorias de despesa"

    def __str__(self):
        return self.nome


CATEGORIAS_INICIAIS = [
    "Material didático e livros", "Material de escritório", "Limpeza e higiene", "Alimentação e merenda",
    "Salários e encargos", "Aluguel", "Água, energia e internet", "Manutenção e reformas",
    "Equipamentos e móveis", "Eventos e passeios", "Marketing e divulgação", "Impostos e taxas",
    "Transporte", "Outros",
]


class Despesa(models.Model):
    """Um gasto da escola (compra de material, livros, contas…)."""

    class Forma(models.TextChoices):
        PIX = "pix", "Pix"
        DINHEIRO = "dinheiro", "Dinheiro"
        CARTAO = "cartao", "Cartão"
        TRANSFERENCIA = "transferencia", "Transferência"
        BOLETO = "boleto", "Boleto"

    data = models.DateField("Data do gasto")
    descricao = models.CharField("Descrição", max_length=150, help_text="Ex.: 30 livros de leitura — Jardim II")
    categoria = models.ForeignKey(CategoriaDespesa, on_delete=models.PROTECT, related_name="despesas", verbose_name="Categoria")
    valor = models.DecimalField("Valor (R$)", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fornecedor = models.CharField("Fornecedor / loja", max_length=120, blank=True)
    forma_pagamento = models.CharField("Forma de pagamento", max_length=15, choices=Forma.choices)
    numero_documento = models.CharField("Nº da nota ou documento", max_length=40, blank=True)
    comprovante = models.FileField(
        "Comprovante (foto ou PDF)", upload_to="despesas/%Y/", blank=True,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"])],
        help_text="Opcional. PDF, JPG, PNG ou WEBP, até 5 MB.")
    observacoes = models.TextField("Observações", blank=True)
    criado_por = models.ForeignKey(dj_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "despesa"
        verbose_name_plural = "despesas"

    def __str__(self):
        return f"{self.descricao} — R$ {self.valor}"

    @property
    def comprovante_e_imagem(self):
        return bool(self.comprovante) and self.comprovante.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
