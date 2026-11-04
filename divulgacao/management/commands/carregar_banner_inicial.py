from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from divulgacao import imagens
from divulgacao.models import Anuncio

TITULO = "Matrículas abertas 2027"


class Command(BaseCommand):
    help = "Cria o anúncio “Matrículas abertas 2027” com a arte de divulgação da escola (não repete se já existir)."

    def handle(self, *args, **options):
        if Anuncio.objects.filter(titulo=TITULO).exists():
            self.stdout.write("O anúncio já existe; nada a fazer.")
            return
        arquivo = Path(__file__).resolve().parents[2] / "exemplos" / "matriculas-2027.png"
        enviado = SimpleUploadedFile(arquivo.name, arquivo.read_bytes(), content_type="image/png")
        anuncio = Anuncio(
            titulo=TITULO, categoria=Anuncio.Categoria.MATRICULAS, destaque=True, ordem=0,
            texto_alternativo="Banner Matrículas abertas 2027 — Escola bilíngue na Praia da Pipa, Margaret School",
        )
        anuncio.imagem = imagens.processar(enviado, lado_maximo=1600, manter_transparencia=True)
        anuncio.save()
        self.stdout.write(self.style.SUCCESS("Anúncio criado. Edite em Divulgação para ajustar datas, texto e botão."))
