from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ConfiguracaoEscola(models.Model):
    """Dados da escola e regras editáveis pela tela de Administração.

    Campos em branco usam o valor padrão de config/settings.py (ou das variáveis de ambiente).
    """

    nome = models.CharField("Nome da escola", max_length=120, blank=True)
    cnpj = models.CharField("CNPJ", max_length=20, blank=True)
    inep = models.CharField("Código INEP", max_length=20, blank=True)
    mantenedora = models.CharField("Mantenedora", max_length=150, blank=True)
    endereco = models.CharField("Endereço", max_length=200, blank=True)
    cidade = models.CharField("Cidade/UF", max_length=80, blank=True,
                              help_text="Aparece na data dos documentos e no foro do contrato. Ex.: Natal/RN")
    telefone = models.CharField("Telefone", max_length=30, blank=True)
    ato_autorizacao = models.CharField(
        "Ato de credenciamento/autorização", max_length=200, blank=True,
        help_text="Ex.: Resolução nº 10/2020 do Conselho Municipal de Educação")
    diretor = models.CharField("Direção (nome)", max_length=120, blank=True)
    diretor_ato = models.CharField("Ato de designação da direção", max_length=150, blank=True)
    secretario = models.CharField("Secretário(a) escolar (nome)", max_length=120, blank=True)
    secretario_ato = models.CharField("Ato de designação do(a) secretário(a)", max_length=150, blank=True)

    instagram = models.CharField("Instagram", max_length=80, blank=True,
                                 help_text="Só o nome do perfil, sem @ e sem endereço. Aparece na página inicial.")
    slogan = models.CharField("Frase de destaque da página inicial", max_length=140, blank=True)
    apresentacao = models.CharField("Texto de apresentação da página inicial", max_length=300, blank=True)

    multa_percentual = models.DecimalField(
        "Multa por atraso (%)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Use 0 para não cobrar. Deixe em branco para usar o padrão do sistema (2%).")
    juros_mensal_percentual = models.DecimalField(
        "Juros ao mês (%)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Proporcional aos dias de atraso. Use 0 para não cobrar. Em branco = padrão (1%).")

    calendario_uf = models.CharField("UF do calendário", max_length=2, blank=True,
                                     help_text="Usada para carregar os feriados estaduais. Ex.: RN")
    calendario_municipio = models.CharField("Município do calendário", max_length=80, blank=True,
                                            help_text="Usado para os feriados municipais. Ex.: Natal")

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuração da escola"
        verbose_name_plural = "configuração da escola"

    def __str__(self):
        return "Configuração da escola"
