from datetime import date

from django.db import models

from .utils import filtrar_por_nome, normalizar


class AlunoQuerySet(models.QuerySet):
    def buscar(self, texto):
        return filtrar_por_nome(self, texto)


class Aluno(models.Model):
    class Sexo(models.TextChoices):
        FEMININO = "F", "Feminino"
        MASCULINO = "M", "Masculino"

    nome = models.CharField("Nome completo", max_length=150)
    data_nascimento = models.DateField("Data de nascimento")
    sexo = models.CharField("Sexo", max_length=1, choices=Sexo.choices, blank=True)
    naturalidade = models.CharField(
        "Naturalidade (cidade/UF)", max_length=100, blank=True,
        help_text="Aparece nos documentos escolares.",
    )
    cpf = models.CharField("CPF da criança", max_length=14, blank=True)
    certidao_nascimento = models.CharField(
        "Certidão de nascimento (número)", max_length=40, blank=True
    )
    endereco = models.CharField("Endereço", max_length=200, blank=True)
    bairro = models.CharField("Bairro", max_length=80, blank=True)
    cidade = models.CharField("Cidade", max_length=80, blank=True)
    foto = models.ImageField("Foto", upload_to="alunos/fotos/", blank=True)

    alergias = models.TextField(
        "Alergias",
        blank=True,
        help_text="Alimentos, medicamentos, picadas etc. Deixe em branco se não houver.",
    )
    observacoes_cuidado = models.TextField(
        "Observações importantes para o cuidado",
        blank=True,
        help_text="Medicação em uso, restrição alimentar, necessidades especiais, rotina de sono etc.",
    )

    nome_busca = models.CharField(max_length=160, blank=True, default="", editable=False, db_index=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = AlunoQuerySet.as_manager()

    class Meta:
        ordering = ["nome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome_busca = normalizar(self.nome)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "nome" in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["nome_busca"]
        super().save(*args, **kwargs)

    @property
    def idade(self):
        hoje, nasc = date.today(), self.data_nascimento
        meses = (hoje.year - nasc.year) * 12 + hoje.month - nasc.month
        if hoje.day < nasc.day:
            meses -= 1
        anos, resto = divmod(max(meses, 0), 12)
        mes_txt = f"{resto} {'mês' if resto == 1 else 'meses'}"
        if anos == 0:
            return mes_txt
        txt = f"{anos} {'ano' if anos == 1 else 'anos'}"
        return f"{txt} e {mes_txt}" if resto else txt

    @property
    def matricula_atual(self):
        """Matrícula do ano letivo mais recente (a ordenação vem do Meta)."""
        return next(iter(self.matriculas.all()), None)

    @property
    def contratante(self):
        """Responsável financeiro; se não houver, o primeiro responsável legal."""
        resp = list(self.responsaveis.all())
        for criterio in (
            lambda r: r.responsavel_financeiro,
            lambda r: r.responsavel_legal,
            lambda r: True,
        ):
            for r in resp:
                if criterio(r):
                    return r
        return None


class Responsavel(models.Model):
    class Parentesco(models.TextChoices):
        MAE = "mae", "Mãe"
        PAI = "pai", "Pai"
        AVO_F = "avo_f", "Avó"
        AVO_M = "avo_m", "Avô"
        TIO = "tio", "Tio(a)"
        TUTOR = "tutor", "Tutor(a) legal"
        OUTRO = "outro", "Outro"

    aluno = models.ForeignKey(
        Aluno, on_delete=models.CASCADE, related_name="responsaveis"
    )
    nome = models.CharField("Nome completo", max_length=150)
    parentesco = models.CharField(
        "Parentesco", max_length=10, choices=Parentesco.choices
    )
    cpf = models.CharField("CPF", max_length=14, blank=True)
    telefone = models.CharField("Telefone / WhatsApp", max_length=20)
    email = models.EmailField("E-mail", blank=True)
    profissao = models.CharField("Profissão", max_length=80, blank=True)
    responsavel_legal = models.BooleanField("Responsável legal", default=True)
    responsavel_financeiro = models.BooleanField(
        "Responsável financeiro (contratante)", default=False
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"

    def __str__(self):
        return f"{self.nome} ({self.get_parentesco_display()})"


class ContatoEmergencia(models.Model):
    aluno = models.ForeignKey(
        Aluno, on_delete=models.CASCADE, related_name="contatos_emergencia"
    )
    nome = models.CharField("Nome", max_length=150)
    parentesco = models.CharField(
        "Relação com a criança", max_length=50, help_text="Ex.: tia, vizinha, madrinha"
    )
    telefone = models.CharField("Telefone", max_length=20)
    autorizado_buscar = models.BooleanField(
        "Autorizado(a) a buscar a criança", default=False
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "contato de emergência"
        verbose_name_plural = "contatos de emergência"

    def __str__(self):
        return f"{self.nome} ({self.parentesco})"
