from django import forms
from django.core.files.uploadedfile import UploadedFile

from core.forms import BootstrapFormMixin

from . import imagens
from .models import Album, Anuncio

MAX_FOTOS_POR_ENVIO = 30


class AnuncioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Anuncio
        fields = ["titulo", "categoria", "imagem", "texto_alternativo", "texto", "botao_texto", "botao_link",
                  "destaque", "ativo", "inicio", "fim", "ordem"]
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 3}),
            "inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fim": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean_imagem(self):
        arquivo = self.cleaned_data.get("imagem")
        if isinstance(arquivo, UploadedFile):  # novo envio: valida, reduz e tira os metadados
            return imagens.processar(arquivo, lado_maximo=1600, manter_transparencia=True)
        return arquivo


class MultiplosArquivos(forms.FileInput):
    allow_multiple_selected = True


class CampoMultiplosArquivos(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiplosArquivos(attrs={"accept": "image/*", "multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpar(d, initial) for d in data if d]
        return [limpar(data, initial)] if data else []


class AlbumForm(BootstrapFormMixin, forms.ModelForm):
    fotos = CampoMultiplosArquivos(
        label="Adicionar fotos", required=False,
        help_text=f"Pode escolher várias de uma vez (até {MAX_FOTOS_POR_ENVIO}). JPG, PNG ou WEBP, até 12 MB cada. "
                  "As fotos são reduzidas e a localização é removida automaticamente.")

    class Meta:
        model = Album
        fields = ["titulo", "descricao", "data_atividade", "visibilidade", "autorizacao_imagem"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 2}),
            "data_atividade": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean_fotos(self):
        arquivos = self.cleaned_data.get("fotos") or []
        if len(arquivos) > MAX_FOTOS_POR_ENVIO:
            raise forms.ValidationError(f"Envie no máximo {MAX_FOTOS_POR_ENVIO} fotos por vez.")
        prontas = []
        for arquivo in arquivos:  # valida tudo antes de gravar qualquer uma
            grande, mini = imagens.versoes(arquivo)
            prontas.append((grande, mini))
        return prontas
