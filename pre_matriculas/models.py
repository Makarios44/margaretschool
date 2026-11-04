import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from alunos.models import Aluno, Responsavel
from matriculas.models import AnoLetivo, Matricula, Turma


def gerar_token():
    return secrets.token_urlsafe(32)

def expiracao_padrao():
    return timezone.now() + timedelta(days=14)


class LinkPreMatricula(models.Model):
    token = models.CharField(max_length=64, unique=True, default=gerar_token, editable=False)
    ano_letivo = models.ForeignKey(AnoLetivo, on_delete=models.PROTECT, related_name="links_pre_matricula")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="links_pre_matricula_criados")
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(default=expiracao_padrao)
    usado_em = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    observacoes_internas = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "link de pré-matrícula"
        verbose_name_plural = "links de pré-matrícula"

    def __str__(self):
        return f"Link para {self.ano_letivo} ({self.criado_em:%d/%m/%Y})"

    @property
    def valido(self):
        return self.ativo and self.usado_em is None and self.expira_em > timezone.now()

    @property
    def situacao(self):
        if not self.ativo:
            return "desativado"
        if self.usado_em:
            return "usado"
        if self.expira_em <= timezone.now():
            return "expirado"
        return "aguardando"

    @property
    def situacao_display(self):
        return {"desativado": "Desativado", "usado": "Usado", "expirado": "Expirado",
                "aguardando": "Aguardando a família"}[self.situacao]


class SolicitacaoPreMatricula(models.Model):
    class Status(models.TextChoices):
        RECEBIDA = "recebida", "Recebida"
        EM_ANALISE = "em_analise", "Em análise"
        APROVADA = "aprovada", "Aprovada"
        REJEITADA = "rejeitada", "Rejeitada"

    link = models.OneToOneField(LinkPreMatricula, on_delete=models.PROTECT, related_name="solicitacao")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEBIDA)
    enviada_em = models.DateTimeField(auto_now_add=True)

    # Dados da criança
    nome_crianca = models.CharField("Nome completo da criança", max_length=150)
    data_nascimento = models.DateField("Data de nascimento")
    sexo = models.CharField("Sexo", max_length=1, choices=(("F", "Feminino"), ("M", "Masculino")), blank=True)
    naturalidade = models.CharField(max_length=100, blank=True)
    certidao_nascimento = models.CharField(max_length=40, blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    bairro = models.CharField(max_length=80, blank=True)
    cidade = models.CharField(max_length=80, blank=True)
    alergias = models.TextField(blank=True)
    observacoes_cuidado = models.TextField(blank=True)

    # Responsável principal
    nome_responsavel = models.CharField("Nome completo do responsável", max_length=150)
    parentesco = models.CharField(max_length=10, choices=(
        ("mae", "Mãe"), ("pai", "Pai"), ("avo_f", "Avó"), ("avo_m", "Avô"),
        ("tio", "Tio(a)"), ("tutor", "Tutor(a) legal"), ("outro", "Outro"),
    ))
    cpf_responsavel = models.CharField(max_length=14, blank=True)
    telefone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    profissao = models.CharField(max_length=80, blank=True)
    endereco_responsavel_diferente = models.BooleanField(default=False)
    responsavel_legal = models.BooleanField(default=True)
    responsavel_financeiro = models.BooleanField(default=True)

    # Contato de emergência (o cadastro do aluno exige ao menos um)
    contato_emergencia_nome = models.CharField("Nome do contato de emergência", max_length=150, blank=True)
    contato_emergencia_parentesco = models.CharField(
        "Relação com a criança", max_length=50, blank=True, help_text="Ex.: tia, vizinha, madrinha")
    contato_emergencia_telefone = models.CharField("Telefone do contato de emergência", max_length=20, blank=True)
    contato_pode_buscar = models.BooleanField("Esta pessoa pode buscar a criança na escola", default=False)

    turma_desejada = models.ForeignKey(Turma, null=True, blank=True, on_delete=models.PROTECT, related_name="solicitacoes_pre_matricula")
    observacoes_familia = models.TextField(blank=True)
    observacoes_secretaria = models.TextField(blank=True)
    aluno_criado = models.ForeignKey(Aluno, null=True, blank=True, on_delete=models.PROTECT, related_name="solicitacoes_pre_matricula")
    matricula_criada = models.ForeignKey(Matricula, null=True, blank=True, on_delete=models.PROTECT, related_name="solicitacoes_origem")

    class Meta:
        ordering = ["-enviada_em"]
        verbose_name = "solicitação de pré-matrícula"
        verbose_name_plural = "solicitações de pré-matrícula"

    def __str__(self):
        return f"{self.nome_crianca} — {self.get_status_display()}"
