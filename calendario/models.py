from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from matriculas.models import AnoLetivo, Turma


class Categoria(models.TextChoices):
    FERIADO_NACIONAL = "feriado_nacional", "Feriado nacional"
    FERIADO_ESTADUAL = "feriado_estadual", "Feriado estadual"
    FERIADO_MUNICIPAL = "feriado_municipal", "Feriado municipal"
    PONTO_FACULTATIVO = "ponto_facultativo", "Ponto facultativo"
    FERIADO_ESCOLAR = "feriado_escolar", "Feriado escolar"
    RECESSO = "recesso", "Recesso / férias escolares"
    SABADO_LETIVO = "sabado_letivo", "Sábado letivo (reposição)"
    MARCO = "marco", "Início / fim de período"
    REUNIAO_PAIS = "reuniao_pais", "Reunião de pais"
    PLANEJAMENTO = "planejamento", "Planejamento / formação da equipe"
    AVALIACAO = "avaliacao", "Avaliações"
    CONSELHO_CLASSE = "conselho_classe", "Conselho de classe"
    ENTREGA_RESULTADOS = "entrega_resultados", "Entrega de boletins / pareceres"
    MATRICULAS = "matriculas", "Matrículas e rematrículas"
    EVENTO = "evento", "Evento / passeio / festividade"
    COMEMORATIVA = "comemorativa", "Data comemorativa"
    OUTRO = "outro", "Outro"


# Categorias que, por padrão, significam "não há aula" (o usuário pode mudar em cada evento).
SEM_AULA_PADRAO = {
    Categoria.FERIADO_NACIONAL, Categoria.FERIADO_ESTADUAL, Categoria.FERIADO_MUNICIPAL,
    Categoria.PONTO_FACULTATIVO, Categoria.FERIADO_ESCOLAR, Categoria.RECESSO,
}
PRIORIDADE = {valor: i for i, valor in enumerate(Categoria.values)}


class PeriodoLetivo(models.Model):
    """Bimestre, trimestre ou semestre do ano letivo."""

    ano_letivo = models.ForeignKey(AnoLetivo, on_delete=models.CASCADE, related_name="periodos")
    nome = models.CharField("Nome", max_length=40, help_text="Ex.: 1º bimestre")
    inicio = models.DateField("Início")
    fim = models.DateField("Fim")

    class Meta:
        ordering = ["inicio"]
        verbose_name = "período letivo"
        verbose_name_plural = "períodos letivos"

    def __str__(self):
        return f"{self.nome} ({self.ano_letivo})"

    def clean(self):
        if self.inicio and self.fim and self.fim < self.inicio:
            raise ValidationError({"fim": "O fim deve ser igual ou depois do início."})


class Evento(models.Model):
    class Origem(models.TextChoices):
        MANUAL = "manual", "Cadastrado pela escola"
        AUTOMATICO = "automatico", "Gerado automaticamente"

    titulo = models.CharField("Título", max_length=120)
    categoria = models.CharField("Categoria", max_length=20, choices=Categoria.choices, default=Categoria.EVENTO)
    data_inicio = models.DateField("Data (ou primeiro dia)")
    data_fim = models.DateField("Último dia", null=True, blank=True, help_text="Deixe em branco se for um dia só.")
    hora_inicio = models.TimeField("Hora de início", null=True, blank=True)
    hora_fim = models.TimeField("Hora de término", null=True, blank=True)
    local = models.CharField("Local", max_length=100, blank=True)
    descricao = models.TextField("Descrição", blank=True)
    sem_aula = models.BooleanField(
        "Não há aula neste(s) dia(s)", default=False,
        help_text="Entra na conta dos dias letivos: esses dias deixam de contar.",
    )
    publico = models.BooleanField(
        "Visível para famílias e visitantes", default=True,
        help_text="Desmarque para eventos internos (só a equipe vê).",
    )
    turmas = models.ManyToManyField(
        Turma, blank=True, related_name="eventos", verbose_name="Turmas",
        help_text="Em branco = vale para toda a escola.",
    )
    repete_anualmente = models.BooleanField(
        "Repete todo ano", default=False,
        help_text="Útil para feriados municipais e aniversário da escola: será copiado ao gerar os feriados de outros anos.",
    )
    origem = models.CharField(max_length=10, choices=Origem.choices, default=Origem.MANUAL, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data_inicio", "hora_inicio", "titulo"]
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        constraints = [
            models.UniqueConstraint(
                fields=["titulo", "data_inicio", "categoria"],
                condition=Q(origem="automatico"),
                name="uniq_evento_automatico",
            )
        ]

    def __str__(self):
        return f"{self.titulo} ({self.data_inicio:%d/%m/%Y})"

    @property
    def ultimo_dia(self):
        return self.data_fim or self.data_inicio

    @property
    def varios_dias(self):
        return self.ultimo_dia != self.data_inicio

    def dias(self):
        d = self.data_inicio
        while d <= self.ultimo_dia:
            yield d
            d += timedelta(days=1)

    @property
    def e_feriado(self):
        return self.categoria in (
            Categoria.FERIADO_NACIONAL, Categoria.FERIADO_ESTADUAL, Categoria.FERIADO_MUNICIPAL,
        )

    @property
    def toda_escola(self):
        return not self.turmas.all()

    def clean(self):
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O último dia deve ser igual ou depois do primeiro."
        if self.hora_inicio and self.hora_fim and not self.varios_dias and self.hora_fim <= self.hora_inicio:
            erros["hora_fim"] = "O término deve ser depois do início."
        if erros:
            raise ValidationError(erros)
