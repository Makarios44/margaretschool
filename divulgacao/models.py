from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


def armazenamento_privado():
    """Pasta fora de MEDIA_ROOT: as fotos só saem pelo sistema, respeitando a visibilidade do álbum."""
    return FileSystemStorage(location=settings.MIDIA_PRIVADA)


class AnuncioQuerySet(models.QuerySet):
    def vigentes(self, hoje=None):
        hoje = hoje or date.today()
        return self.filter(ativo=True, inicio__lte=hoje).filter(models.Q(fim__isnull=True) | models.Q(fim__gte=hoje))


class Anuncio(models.Model):
    """Anúncio da página inicial: rematrícula, evento, aviso, novidade…"""

    class Categoria(models.TextChoices):
        MATRICULAS = "matriculas", "Matrículas e rematrículas"
        EVENTO = "evento", "Evento"
        AVISO = "aviso", "Aviso"
        NOVIDADE = "novidade", "Novidade"
        OUTRO = "outro", "Outro"

    titulo = models.CharField("Título", max_length=120)
    texto = models.TextField("Texto (opcional)", max_length=600, blank=True,
                             help_text="Curto e direto. Se o banner já tem todo o texto, pode deixar em branco.")
    categoria = models.CharField("Categoria", max_length=12, choices=Categoria.choices, default=Categoria.AVISO)
    imagem = models.ImageField("Imagem / banner (opcional)", upload_to="anuncios/%Y/", blank=True,
                               help_text="JPG, PNG ou WEBP. Ex.: a arte que será impressa para divulgação.")
    texto_alternativo = models.CharField(
        "Descrição da imagem", max_length=200, blank=True,
        help_text="Para quem usa leitor de tela. Ex.: Banner “Matrículas abertas 2027”. Em branco usa o título.")
    botao_texto = models.CharField("Texto do botão (opcional)", max_length=40, blank=True)
    botao_link = models.CharField("Link do botão", max_length=300, blank=True,
                                  help_text="Endereço completo (https://…) ou um caminho do site (ex.: /calendario/).")
    destaque = models.BooleanField("Mostrar no topo da página inicial (carrossel)", default=True,
                                   help_text="Desmarcado, aparece só na lista de novidades.")
    ativo = models.BooleanField("Ativo", default=True)
    inicio = models.DateField("Começa a aparecer em", default=date.today)
    fim = models.DateField("Aparece até (opcional)", null=True, blank=True,
                           help_text="Depois desta data o anúncio sai do ar sozinho. Em branco = sem data para acabar.")
    ordem = models.PositiveSmallIntegerField("Ordem", default=0, help_text="Número menor aparece primeiro.")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = AnuncioQuerySet.as_manager()

    class Meta:
        ordering = ["ordem", "-inicio", "-id"]
        verbose_name = "anúncio"
        verbose_name_plural = "anúncios"

    def __str__(self):
        return self.titulo

    @property
    def situacao(self):
        hoje = date.today()
        if not self.ativo:
            return "desativado"
        if self.inicio > hoje:
            return "agendado"
        if self.fim and self.fim < hoje:
            return "encerrado"
        return "no_ar"

    @property
    def situacao_display(self):
        return {"desativado": "Desativado", "agendado": "Agendado", "encerrado": "Encerrado", "no_ar": "No ar"}[self.situacao]

    @property
    def alt(self):
        return self.texto_alternativo or self.titulo

    def clean(self):
        erros = {}
        if self.inicio and self.fim and self.fim < self.inicio:
            erros["fim"] = "A data final deve ser igual ou depois da data de início."
        if bool(self.botao_texto) != bool(self.botao_link):
            erros["botao_link" if self.botao_texto else "botao_texto"] = "Preencha o texto e o link do botão (ou deixe os dois em branco)."
        link = (self.botao_link or "").strip()
        if link and not (link.startswith(("https://", "http://")) or (link.startswith("/") and not link.startswith("//"))):
            erros["botao_link"] = "Use um endereço começando com https:// ou um caminho do site começando com /."
        if erros:
            raise ValidationError(erros)


class Album(models.Model):
    """Álbum de fotos de atividades. As imagens são privadas: só saem pelo sistema, conforme a visibilidade."""

    class Visibilidade(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho (só a equipe vê)"
        LOGADOS = "logados", "Só quem tem login (famílias e equipe)"
        PUBLICO = "publico", "Qualquer pessoa (aparece no site)"

    titulo = models.CharField("Título", max_length=120, help_text="Ex.: Festa junina 2026")
    descricao = models.TextField("Descrição (opcional)", max_length=500, blank=True)
    data_atividade = models.DateField("Data da atividade", default=date.today)
    visibilidade = models.CharField("Quem pode ver", max_length=10, choices=Visibilidade.choices, default=Visibilidade.RASCUNHO)
    autorizacao_imagem = models.BooleanField(
        "Confirmo que os responsáveis das crianças que aparecem autorizaram o uso das imagens", default=False,
        help_text="Obrigatório para publicar. Evite escrever nomes completos de crianças nas legendas.")
    capa = models.ForeignKey("Foto", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_atividade", "-id"]
        verbose_name = "álbum"
        verbose_name_plural = "álbuns"

    def __str__(self):
        return self.titulo

    def clean(self):
        if self.visibilidade != self.Visibilidade.RASCUNHO and not self.autorizacao_imagem:
            raise ValidationError({"autorizacao_imagem": "Para publicar o álbum, confirme a autorização de uso de imagem."})

    @property
    def foto_capa(self):
        return self.capa or self.fotos.first()

    def visivel_para(self, usuario):
        if usuario.is_authenticated and usuario.is_staff:
            return True
        if self.visibilidade == self.Visibilidade.PUBLICO:
            return True
        return self.visibilidade == self.Visibilidade.LOGADOS and usuario.is_authenticated

    @classmethod
    def visiveis_para(cls, usuario):
        if usuario.is_authenticated and usuario.is_staff:
            return cls.objects.all()
        permitidas = [cls.Visibilidade.PUBLICO]
        if usuario.is_authenticated:
            permitidas.append(cls.Visibilidade.LOGADOS)
        return cls.objects.filter(visibilidade__in=permitidas)


class Foto(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="fotos")
    imagem = models.ImageField(upload_to="galeria/%Y/%m/", storage=armazenamento_privado)
    miniatura = models.ImageField(upload_to="galeria/mini/%Y/%m/", storage=armazenamento_privado)
    legenda = models.CharField("Legenda", max_length=200, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "foto"
        verbose_name_plural = "fotos"

    def __str__(self):
        return self.legenda or f"Foto {self.pk}"


@receiver(post_delete, sender=Foto)
def apagar_arquivos_da_foto(sender, instance, **kwargs):
    """Ao excluir a foto (ou o álbum), os arquivos também saem do disco."""
    for campo in (instance.imagem, instance.miniatura):
        if campo:
            campo.delete(save=False)
