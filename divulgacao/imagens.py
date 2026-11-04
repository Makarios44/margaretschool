"""Tratamento de imagens enviadas: valida, reduz, corrige a rotação e remove os metadados (EXIF/GPS).

Fotos de celular carregam a localização de onde foram tiradas. Reconstruir a imagem do zero descarta isso.
"""
import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 50_000_000  # protege contra arquivos "bomba" que estouram a memória

TAMANHO_MAXIMO = 12 * 1024 * 1024  # 12 MB por arquivo enviado


def abrir(arquivo):
    """Abre o arquivo como imagem (e só aceita imagens de verdade, não importa a extensão)."""
    if getattr(arquivo, "size", 0) > TAMANHO_MAXIMO:
        raise ValidationError(f"“{arquivo.name}” é maior que 12 MB. Envie uma versão menor.")
    try:
        arquivo.seek(0)
        imagem = Image.open(arquivo)
        imagem.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError, SyntaxError):
        raise ValidationError(f"“{getattr(arquivo, 'name', 'arquivo')}” não é uma imagem válida (use JPG, PNG ou WEBP).")
    return ImageOps.exif_transpose(imagem)


def _tem_transparencia(imagem):
    return imagem.mode in ("RGBA", "LA") or (imagem.mode == "P" and "transparency" in imagem.info)


def processar(arquivo, lado_maximo=1600, qualidade=86, manter_transparencia=False):
    """Devolve um ContentFile com a imagem reduzida, sem metadados. PNG só se for preciso manter transparência."""
    imagem = abrir(arquivo)
    usar_png = manter_transparencia and _tem_transparencia(imagem)
    imagem.thumbnail((lado_maximo, lado_maximo), Image.LANCZOS)
    saida = io.BytesIO()
    if usar_png:
        imagem.convert("RGBA").save(saida, "PNG", optimize=True)
        extensao = "png"
    else:
        if _tem_transparencia(imagem):  # fundo branco no lugar da transparência
            fundo = Image.new("RGB", imagem.size, "white")
            fundo.paste(imagem.convert("RGBA"), mask=imagem.convert("RGBA").split()[-1])
            imagem = fundo
        imagem.convert("RGB").save(saida, "JPEG", quality=qualidade, optimize=True, progressive=True)
        extensao = "jpg"
    return ContentFile(saida.getvalue(), name=f"{uuid.uuid4().hex}.{extensao}")


def _codificar(imagem, lado, qualidade=86):
    copia = imagem.copy()
    copia.thumbnail((lado, lado), Image.LANCZOS)
    if _tem_transparencia(copia):
        fundo = Image.new("RGB", copia.size, "white")
        rgba = copia.convert("RGBA")
        fundo.paste(rgba, mask=rgba.split()[-1])
        copia = fundo
    saida = io.BytesIO()
    copia.convert("RGB").save(saida, "JPEG", quality=qualidade, optimize=True, progressive=True)
    return ContentFile(saida.getvalue(), name=f"{uuid.uuid4().hex}.jpg")


def versoes(arquivo, lado=1600, lado_miniatura=480):
    """Abre a foto uma vez e devolve (imagem_grande, miniatura), ambas sem metadados."""
    imagem = abrir(arquivo)
    return _codificar(imagem, lado), _codificar(imagem, lado_miniatura, qualidade=80)
