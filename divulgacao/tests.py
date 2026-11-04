import io
import os
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.contato import links_contato

from . import imagens
from .models import Album, Anuncio, Foto

HOJE = date.today()
MEDIA = tempfile.mkdtemp()
PRIVADA = tempfile.mkdtemp()


def jpg(largura=800, altura=600, cor="red", exif=False, orientacao=None, nome="foto.jpg"):
    buf = io.BytesIO()
    img = Image.new("RGB", (largura, altura), cor)
    dados = {}
    if exif or orientacao:
        e = Image.Exif()
        if exif:
            e[0x010F] = "FabricanteSecreto"  # Make
            e[0x8825] = {1: "S", 2: (6.0, 12.0, 0.0), 3: "W", 4: (35.0, 6.0, 0.0)}  # GPS
        if orientacao:
            e[0x0112] = orientacao
        dados["exif"] = e
    img.save(buf, "JPEG", **dados)
    return SimpleUploadedFile(nome, buf.getvalue(), content_type="image/jpeg")


def png_transparente():
    buf = io.BytesIO()
    Image.new("RGBA", (100, 80), (255, 0, 0, 0)).save(buf, "PNG")
    return SimpleUploadedFile("t.png", buf.getvalue(), content_type="image/png")


def abrir_bytes(conteudo):
    return Image.open(io.BytesIO(conteudo.read() if hasattr(conteudo, "read") else conteudo))


@override_settings(MEDIA_ROOT=MEDIA, MIDIA_PRIVADA=PRIVADA)
class Base(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # o armazenamento das fotos é definido ao carregar o modelo; aponta para a pasta temporária dos testes
        cls._campos = [(Foto._meta.get_field(n), Foto._meta.get_field(n).storage) for n in ("imagem", "miniatura")]
        for campo, _ in cls._campos:
            campo.storage = FileSystemStorage(location=PRIVADA)

    @classmethod
    def tearDownClass(cls):
        for campo, original in cls._campos:
            campo.storage = original
        shutil.rmtree(MEDIA, ignore_errors=True)
        shutil.rmtree(PRIVADA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user("sec", password="x", is_staff=True)
        self.pai = U.objects.create_user("pai", password="x")

    def anuncio(self, titulo="Rematrícula", **kw):
        kw.setdefault("inicio", HOJE - timedelta(days=1))
        return Anuncio.objects.create(titulo=titulo, **kw)

    def album(self, visibilidade="publico", fotos=2, titulo="Festa junina", autorizacao=True):
        a = Album.objects.create(titulo=titulo, visibilidade=visibilidade, autorizacao_imagem=autorizacao)
        for i in range(fotos):
            g, m = imagens.versoes(jpg(cor=("red", "blue", "green")[i % 3]))
            Foto.objects.create(album=a, imagem=g, miniatura=m, ordem=i)
        if fotos:
            a.capa = a.fotos.first()
            a.save()
        return a


class ImagensTests(Base):
    def test_reduz_e_remove_metadados_de_localizacao(self):
        original = jpg(3000, 2000, exif=True)
        assert Image.open(io.BytesIO(original.read())).getexif().get(0x010F) == "FabricanteSecreto"
        original.seek(0)
        saida = imagens.processar(original, lado_maximo=1600)
        img = abrir_bytes(saida)
        self.assertEqual(max(img.size), 1600)
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(dict(img.getexif()), {})  # sem fabricante, sem GPS
        self.assertTrue(saida.name.endswith(".jpg"))

    def test_nao_aumenta_imagem_pequena(self):
        self.assertEqual(abrir_bytes(imagens.processar(jpg(300, 200))).size, (300, 200))

    def test_aplica_a_rotacao_do_celular(self):
        img = abrir_bytes(imagens.processar(jpg(400, 200, orientacao=6)))  # 6 = girar 90°
        self.assertEqual(img.size, (200, 400))

    def test_rejeita_arquivo_que_nao_e_imagem(self):
        falso = SimpleUploadedFile("foto.jpg", b"isto nao e uma imagem", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            imagens.processar(falso)
        script = SimpleUploadedFile("x.png", b"<script>alert(1)</script>", content_type="image/png")
        with self.assertRaises(ValidationError):
            imagens.abrir(script)

    def test_rejeita_arquivo_muito_grande(self):
        grande = SimpleUploadedFile("g.jpg", b"0" * (12 * 1024 * 1024 + 1), content_type="image/jpeg")
        with self.assertRaisesMessage(ValidationError, "maior que 12 MB"):
            imagens.abrir(grande)

    def test_transparencia(self):
        png = abrir_bytes(imagens.processar(png_transparente(), manter_transparencia=True))
        self.assertEqual((png.format, png.mode), ("PNG", "RGBA"))
        jpeg = abrir_bytes(imagens.processar(png_transparente()))
        self.assertEqual(jpeg.format, "JPEG")
        self.assertEqual(jpeg.convert("RGB").getpixel((5, 5)), (255, 255, 255))  # fundo branco

    def test_versoes_grande_e_miniatura(self):
        grande, mini = imagens.versoes(jpg(3000, 2000, exif=True))
        self.assertEqual(max(abrir_bytes(grande).size), 1600)
        self.assertEqual(max(abrir_bytes(mini).size), 480)
        grande.seek(0)
        self.assertEqual(dict(abrir_bytes(grande).getexif()), {})


class ContatoTests(TestCase):
    def test_links_a_partir_dos_dados_da_escola(self):
        c = links_contato({"telefone": "(84) 99165-8059", "endereco": "Rua Travessa dos Flamingos, nº 79 — Praia da Pipa",
                           "cidade": "Tibau do Sul/RN", "instagram": "@escola.exemplo"})
        self.assertEqual(c["whatsapp"], "https://wa.me/5584991658059")
        self.assertEqual(c["tel"], "tel:+5584991658059")
        self.assertEqual(c["instagram"], "https://www.instagram.com/escola.exemplo/")
        self.assertIn("google.com/maps/search", c["mapa"])
        self.assertIn("Tibau%20do%20Sul", c["mapa"])

    def test_variacoes_e_ausencias(self):
        self.assertEqual(links_contato({"telefone": "+55 84 99165-8059"})["whatsapp"], "https://wa.me/5584991658059")
        self.assertEqual(links_contato({"telefone": "99165"})["whatsapp"], "")
        self.assertEqual(links_contato({"instagram": "https://www.instagram.com/perfil.x/?hl=pt"})["instagram_perfil"], "perfil.x")
        vazio = links_contato({})
        self.assertEqual((vazio["whatsapp"], vazio["instagram"], vazio["mapa"]), ("", "", ""))


class AnuncioModeloTests(Base):
    def test_vigencia_e_situacao(self):
        no_ar = self.anuncio("A")
        sem_fim = self.anuncio("B", fim=None)
        agendado = self.anuncio("C", inicio=HOJE + timedelta(days=3))
        encerrado = self.anuncio("D", inicio=HOJE - timedelta(days=9), fim=HOJE - timedelta(days=1))
        desativado = self.anuncio("E", ativo=False)
        ultimo_dia = self.anuncio("F", fim=HOJE)  # ainda vale no último dia
        self.assertEqual({a.titulo for a in Anuncio.objects.vigentes()}, {"A", "B", "F"})
        self.assertEqual([a.situacao for a in (no_ar, agendado, encerrado, desativado, ultimo_dia)],
                         ["no_ar", "agendado", "encerrado", "desativado", "no_ar"])

    def test_validacoes(self):
        def erros(**kw):
            a = Anuncio(titulo="x", inicio=HOJE, **kw)
            with self.assertRaises(ValidationError) as ctx:
                a.full_clean()
            return ctx.exception.message_dict
        self.assertIn("fim", erros(fim=HOJE - timedelta(days=1)))
        self.assertIn("botao_link", erros(botao_texto="Clique"))
        self.assertIn("botao_texto", erros(botao_link="https://x.com"))
        for ruim in ("javascript:alert(1)", "//evil.com/x", "data:text/html,x", "ftp://x.com", "evil.com"):
            self.assertIn("botao_link", erros(botao_texto="Ir", botao_link=ruim), ruim)
        for bom in ("https://wa.me/5584991658059", "http://exemplo.com", "/calendario/"):
            Anuncio(titulo="x", inicio=HOJE, botao_texto="Ir", botao_link=bom).full_clean()


class AnuncioGestaoTests(Base):
    def dados(self, **kw):
        d = {"titulo": "Rematrícula 2027", "categoria": "matriculas", "destaque": "on", "ativo": "on",
             "inicio": HOJE.isoformat(), "ordem": 0}
        d.update(kw)
        return d

    def test_criar_com_imagem_alterar_desativar_e_excluir(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse("anuncio_create"), self.dados(imagem=jpg(2400, 1200, exif=True)))
        self.assertEqual(r.status_code, 302)
        a = Anuncio.objects.get()
        self.assertEqual(a.criado_por, self.staff)
        self.assertTrue(os.path.exists(a.imagem.path))
        self.assertEqual(max(Image.open(a.imagem.path).size), 1600)
        self.assertEqual(dict(Image.open(a.imagem.path).getexif()), {})
        self.client.post(reverse("anuncio_update", args=[a.pk]), self.dados(titulo="Novo título", botao_texto="Falar", botao_link="https://wa.me/55"))
        a.refresh_from_db()
        self.assertEqual((a.titulo, a.botao_texto), ("Novo título", "Falar"))
        self.assertTrue(a.imagem)  # sem novo envio, a imagem continua
        self.assertEqual(self.client.get(reverse("anuncio_ativo", args=[a.pk])).status_code, 405)
        self.client.post(reverse("anuncio_ativo", args=[a.pk]))
        a.refresh_from_db()
        self.assertFalse(a.ativo)
        self.assertContains(self.client.get(reverse("divulgacao")), "Desativado")
        self.client.post(reverse("anuncio_delete", args=[a.pk]))
        self.assertFalse(Anuncio.objects.exists())

    def test_imagem_invalida_e_validacoes_no_formulario(self):
        self.client.force_login(self.staff)
        falso = SimpleUploadedFile("x.jpg", b"nao sou imagem", content_type="image/jpeg")
        self.assertContains(self.client.post(reverse("anuncio_create"), self.dados(imagem=falso)), "imagem")
        self.assertContains(self.client.post(reverse("anuncio_create"), self.dados(botao_texto="Ir", botao_link="javascript:alert(1)")), "https://")
        self.assertContains(self.client.post(reverse("anuncio_create"), self.dados(fim=(HOJE - timedelta(days=2)).isoformat())), "igual ou depois")
        self.assertFalse(Anuncio.objects.exists())

    def test_somente_equipe(self):
        a = self.anuncio()
        alvos = [("divulgacao", []), ("anuncio_create", []), ("anuncio_update", [a.pk]), ("album_list", []), ("album_create", [])]
        self.client.force_login(self.pai)
        for nome, args in alvos:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 403, nome)
        self.assertEqual(self.client.post(reverse("anuncio_delete", args=[a.pk])).status_code, 403)
        self.client.logout()
        for nome, args in alvos:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 302, nome)


class HomeTests(Base):
    def test_sem_anuncios_mostra_a_apresentacao_da_escola(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Escolher uma escola vai muito além do ensino.")
        self.assertNotContains(r, "carrossel-anuncios")
        self.assertContains(r, "https://wa.me/5584991658059")  # contato a partir do telefone cadastrado
        self.assertContains(r, "Como chegar")
        self.assertNotContains(r, "Você é da equipe")

    def test_so_aparece_o_que_esta_no_ar(self):
        self.anuncio("No ar", destaque=True)
        self.anuncio("Futuro", destaque=True, inicio=HOJE + timedelta(days=2))
        self.anuncio("Encerrado", destaque=True, inicio=HOJE - timedelta(days=9), fim=HOJE - timedelta(days=1))
        self.anuncio("Inativo", destaque=True, ativo=False)
        self.anuncio("Só novidade", destaque=False, texto="Texto da novidade")
        r = self.client.get(reverse("home"))
        self.assertEqual([a.titulo for a in r.context["destaques"]], ["No ar"])
        self.assertEqual([a.titulo for a in r.context["novidades"]], ["Só novidade"])
        for oculto in ("Futuro", "Encerrado", "Inativo"):
            self.assertNotContains(r, oculto)
        self.assertContains(r, "Avisos e novidades")

    def test_carrossel_com_varios_banners_e_alternativa_em_texto(self):
        for i, nome in enumerate(("Primeiro", "Segundo")):
            a = self.anuncio(nome, destaque=True, ordem=i, texto_alternativo=f"Banner {nome}")
            a.imagem = imagens.processar(jpg())
            a.save()
        r = self.client.get(reverse("home"))
        self.assertContains(r, 'alt="Banner Primeiro"')
        self.assertContains(r, 'alt="Banner Segundo"')
        self.assertContains(r, "carousel-indicators")
        self.assertContains(r, 'class="visually-hidden">Primeiro</h2>')  # banner sozinho: título só para leitores de tela
        unico = Anuncio.objects.exclude(titulo="Primeiro").delete()
        self.assertNotContains(self.client.get(reverse("home")), "carousel-indicators")

    def test_texto_e_botao_aparecem_e_html_e_escapado(self):
        self.anuncio("<script>alert(1)</script>", texto="Venha <b>conhecer</b>", botao_texto="Falar", botao_link="https://wa.me/55")
        r = self.client.get(reverse("home"))
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")
        self.assertContains(r, "&lt;b&gt;conhecer&lt;/b&gt;")
        self.assertContains(r, 'href="https://wa.me/55"')

    def test_eventos_publicos_e_fotos_publicas_na_home(self):
        from calendario.models import Evento
        Evento.objects.create(titulo="Reunião de pais", categoria="reuniao_pais", data_inicio=HOJE + timedelta(days=5))
        Evento.objects.create(titulo="Planejamento interno", categoria="planejamento", data_inicio=HOJE + timedelta(days=6), publico=False)
        publico = self.album("publico", titulo="Álbum aberto")
        self.album("logados", titulo="Álbum das famílias")
        self.album("rascunho", titulo="Álbum rascunho", autorizacao=False)
        self.album("publico", fotos=0, titulo="Álbum vazio")
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Reunião de pais")
        self.assertNotContains(r, "Planejamento interno")
        self.assertContains(r, "Álbum aberto")
        self.assertContains(r, reverse("foto_arquivo", args=[publico.capa_id, "mini"]))
        for escondido in ("Álbum das famílias", "Álbum rascunho", "Álbum vazio"):
            self.assertNotContains(r, escondido)

    def test_barra_da_equipe_so_para_equipe(self):
        self.client.force_login(self.pai)
        self.assertNotContains(self.client.get(reverse("home")), "Você é da equipe")
        self.client.force_login(self.staff)
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Você é da equipe")
        self.assertContains(r, reverse("anuncio_create"))

    def test_avisos_publicos(self):
        self.anuncio("Aviso vigente", texto="Detalhes")
        self.anuncio("Aviso antigo", inicio=HOJE - timedelta(days=9), fim=HOJE - timedelta(days=2))
        r = self.client.get(reverse("avisos"))
        self.assertContains(r, "Aviso vigente")
        self.assertNotContains(r, "Aviso antigo")


class AlbumGestaoTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def dados(self, **kw):
        d = {"titulo": "Passeio à praia", "data_atividade": HOJE.isoformat(), "visibilidade": "rascunho"}
        d.update(kw)
        return d

    def test_criar_album_com_varias_fotos_guardadas_fora_da_pasta_publica(self):
        r = self.client.post(reverse("album_create"), self.dados(fotos=[jpg(3000, 2000, exif=True, nome="a.jpg"), jpg(nome="b.jpg"), jpg(nome="c.jpg")]))
        a = Album.objects.get()
        self.assertRedirects(r, reverse("album_update", args=[a.pk]))
        self.assertEqual(a.fotos.count(), 3)
        self.assertIsNotNone(a.capa)
        foto = a.fotos.first()
        self.assertTrue(foto.imagem.path.startswith(PRIVADA))
        self.assertFalse(foto.imagem.path.startswith(MEDIA))
        self.assertEqual(max(Image.open(foto.imagem.path).size), 1600)
        self.assertEqual(max(Image.open(foto.miniatura.path).size), 480)
        self.assertEqual(dict(Image.open(foto.imagem.path).getexif()), {})

    def test_publicar_exige_autorizacao_de_imagem(self):
        for visibilidade in ("logados", "publico"):
            r = self.client.post(reverse("album_create"), self.dados(visibilidade=visibilidade))
            self.assertContains(r, "confirme a autorização")
        self.assertFalse(Album.objects.exists())
        self.client.post(reverse("album_create"), self.dados(visibilidade="publico", autorizacao_imagem="on"))
        self.assertEqual(Album.objects.get().visibilidade, "publico")

    def test_um_arquivo_ruim_bloqueia_o_envio_inteiro(self):
        falso = SimpleUploadedFile("c.jpg", b"nao e imagem", content_type="image/jpeg")
        r = self.client.post(reverse("album_create"), self.dados(fotos=[jpg(nome="a.jpg"), falso]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "não é uma imagem válida")
        self.assertFalse(Album.objects.exists())
        self.assertFalse(Foto.objects.exists())

    def test_limite_de_trinta_fotos_por_envio(self):
        r = self.client.post(reverse("album_create"), self.dados(fotos=[jpg(50, 50, nome=f"{i}.jpg") for i in range(31)]))
        self.assertContains(r, "no máximo 30")
        self.assertFalse(Album.objects.exists())

    def test_legenda_capa_remocao_e_novas_fotos(self):
        a = self.album("rascunho", fotos=3, autorizacao=False)
        f1, f2, f3 = a.fotos.all()
        removida = f3.imagem.path
        self.assertTrue(os.path.exists(removida))
        r = self.client.post(reverse("album_update", args=[a.pk]), self.dados(
            fotos=[jpg(nome="nova.jpg")], capa=f2.pk, **{f"legenda_{f1.pk}": "Brincadeira no pátio", f"remover_{f3.pk}": "on"}))
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        self.assertEqual(a.capa_id, f2.pk)
        self.assertEqual(Foto.objects.get(pk=f1.pk).legenda, "Brincadeira no pátio")
        self.assertFalse(Foto.objects.filter(pk=f3.pk).exists())
        self.assertFalse(os.path.exists(removida))  # o arquivo também sai do disco
        self.assertEqual(a.fotos.count(), 3)  # 3 - 1 removida + 1 nova

    def test_remover_a_capa_escolhe_outra(self):
        a = self.album("rascunho", fotos=2, autorizacao=False)
        capa = a.capa
        self.client.post(reverse("album_update", args=[a.pk]), self.dados(**{f"remover_{capa.pk}": "on"}))
        a.refresh_from_db()
        self.assertIsNotNone(a.capa_id)
        self.assertNotEqual(a.capa_id, capa.pk)

    def test_excluir_album_apaga_as_fotos_do_disco(self):
        a = self.album("rascunho", fotos=2, autorizacao=False)
        caminhos = [f.imagem.path for f in a.fotos.all()] + [f.miniatura.path for f in a.fotos.all()]
        self.assertEqual(self.client.get(reverse("album_delete", args=[a.pk])).status_code, 405)
        self.client.post(reverse("album_delete", args=[a.pk]))
        self.assertFalse(Album.objects.exists() or Foto.objects.exists())
        self.assertFalse(any(os.path.exists(c) for c in caminhos))


class VisibilidadeTests(Base):
    def acessos(self, album):
        foto = album.fotos.first()
        return {
            "lista": self.client.get(reverse("galeria")),
            "album": self.client.get(reverse("album_detail", args=[album.pk])),
            "foto": self.client.get(reverse("foto_arquivo", args=[foto.pk, "grande"])),
            "mini": self.client.get(reverse("foto_arquivo", args=[foto.pk, "mini"])),
        }

    def test_album_publico_qualquer_pessoa(self):
        a = self.album("publico", titulo="Aberto")
        r = self.acessos(a)
        self.assertContains(r["lista"], "Aberto")
        self.assertEqual((r["album"].status_code, r["foto"].status_code, r["mini"].status_code), (200, 200, 200))
        self.assertEqual(r["foto"]["Content-Type"], "image/jpeg")
        self.assertEqual(r["foto"]["Cache-Control"], "public, max-age=86400")
        self.assertEqual(r["foto"]["X-Content-Type-Options"], "nosniff")
        self.assertTrue(b"".join(r["foto"].streaming_content).startswith(b"\xff\xd8"))  # é um JPEG de verdade

    def test_album_so_para_logados(self):
        a = self.album("logados", titulo="Famílias")
        anonimo = self.acessos(a)
        self.assertNotContains(anonimo["lista"], "Famílias")
        self.assertEqual(anonimo["album"].status_code, 302)
        self.assertIn("/entrar/", anonimo["album"]["Location"])
        self.assertEqual((anonimo["foto"].status_code, anonimo["mini"].status_code), (404, 404))  # a imagem não vaza
        self.client.force_login(self.pai)
        logado = self.acessos(a)
        self.assertContains(logado["lista"], "Famílias")
        self.assertEqual((logado["album"].status_code, logado["foto"].status_code), (200, 200))
        self.assertEqual(logado["foto"]["Cache-Control"], "private, max-age=3600")

    def test_rascunho_so_a_equipe(self):
        a = self.album("rascunho", titulo="Rascunho secreto", autorizacao=False)
        for papel in (None, self.pai):
            if papel:
                self.client.force_login(papel)
            r = self.acessos(a)
            self.assertNotContains(r["lista"], "Rascunho secreto")
            self.assertEqual((r["album"].status_code, r["foto"].status_code), (404, 404))
        self.client.force_login(self.staff)
        r = self.acessos(a)
        self.assertContains(r["lista"], "Rascunho secreto")
        self.assertEqual((r["album"].status_code, r["foto"].status_code), (200, 200))

    def test_album_vazio_so_aparece_para_a_equipe(self):
        self.album("publico", fotos=0, titulo="Sem fotos")
        self.assertNotContains(self.client.get(reverse("galeria")), "Sem fotos")
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("galeria")), "Sem fotos")

    def test_tipo_invalido_e_arquivo_ausente(self):
        a = self.album("publico")
        foto = a.fotos.first()
        self.assertEqual(self.client.get(reverse("foto_arquivo", args=[foto.pk, "original"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("foto_arquivo", args=[99999, "mini"])).status_code, 404)
        os.remove(foto.imagem.path)
        self.assertEqual(self.client.get(reverse("foto_arquivo", args=[foto.pk, "grande"])).status_code, 404)

    def test_visualizacao_ampliada_na_pagina_do_album(self):
        a = self.album("publico", fotos=2)
        f = a.fotos.first()
        f.legenda = "Ciranda"
        f.save()
        r = self.client.get(reverse("album_detail", args=[a.pk]))
        self.assertContains(r, 'id="lightbox"')
        self.assertContains(r, f'data-foto-grande="{reverse("foto_arquivo", args=[f.pk, "grande"])}"')
        self.assertContains(r, 'data-legenda="Ciranda"')
        self.assertContains(r, "galeria.js")


class BannerInicialTests(Base):
    def test_comando_cria_o_anuncio_uma_vez(self):
        call_command("carregar_banner_inicial", stdout=io.StringIO())
        call_command("carregar_banner_inicial", stdout=io.StringIO())
        a = Anuncio.objects.get()
        self.assertEqual((a.titulo, a.categoria, a.destaque), ("Matrículas abertas 2027", "matriculas", True))
        self.assertTrue(os.path.exists(a.imagem.path))
        self.assertLessEqual(max(Image.open(a.imagem.path).size), 1600)
        self.assertContains(self.client.get(reverse("home")), "Banner Matrículas abertas 2027")

    def test_painel_tem_atalhos(self):
        self.client.force_login(self.pai)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, reverse("galeria"))
        self.assertContains(r, reverse("avisos"))
        self.assertNotContains(r, reverse("divulgacao"))
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("dashboard")), reverse("divulgacao"))


class ApresentacaoDinamicaTests(TestCase):
    """Home: apresentação completa sem anúncios no ar, compacta com algum."""

    def anuncio(self, titulo="A", **kw):
        return Anuncio.objects.create(titulo=titulo, **kw)

    def get(self):
        return self.client.get(reverse("home"), SERVER_NAME="localhost")

    def test_sem_anuncios_apresentacao_completa(self):
        r = self.get()
        self.assertContains(r, "hero-art")
        self.assertNotContains(r, "hero-compacto")
        self.assertNotContains(r, "carrossel-anuncios")
        self.assertNotContains(r, "titulo-novidades")
        self.assertContains(r, "Informações sobre matrículas")

    def test_so_destaques(self):
        self.anuncio(destaque=True)
        r = self.get()
        self.assertContains(r, "carrossel-anuncios")
        self.assertContains(r, "hero-compacto")
        self.assertNotContains(r, "hero-art")
        self.assertNotContains(r, "titulo-novidades")

    def test_so_novidades(self):
        self.anuncio(destaque=False)
        r = self.get()
        self.assertContains(r, "titulo-novidades")
        self.assertContains(r, "hero-compacto")
        self.assertNotContains(r, "hero-art")
        self.assertNotContains(r, "carrossel-anuncios")

    def test_destaques_e_novidades_sem_duplicar(self):
        self.anuncio("Destacado", destaque=True)
        self.anuncio("Novidade comum", destaque=False)
        r = self.get()
        self.assertContains(r, "carrossel-anuncios")
        self.assertContains(r, "titulo-novidades")
        self.assertContains(r, "hero-compacto")
        self.assertEqual(r.content.decode().count("<h2>Destacado</h2>"), 1)
        self.assertNotContains(r, "<h3>Destacado</h3>")
        self.assertContains(r, "<h3>Novidade comum</h3>")
        # slogan e botões continuam
        self.assertContains(r, "hero-title")
        self.assertContains(r, "Informações sobre matrículas")

    def test_inativos_futuros_e_expirados_nao_mudam_o_layout(self):
        self.anuncio("Off", ativo=False)
        self.anuncio("Futuro", inicio=HOJE + timedelta(days=3))
        self.anuncio("Velho", inicio=HOJE - timedelta(days=9), fim=HOJE - timedelta(days=1), destaque=False)
        r = self.get()
        self.assertContains(r, "hero-art")
        self.assertNotContains(r, "hero-compacto")
        for t in ("Off", "Futuro", "Velho"):
            self.assertNotContains(r, f">{t}<")

    def test_ordem_das_secoes(self):
        self.anuncio("Dest", destaque=True)
        self.anuncio("Nov", destaque=False)
        h = self.get().content.decode()
        self.assertLess(h.index("carrossel-anuncios"), h.index('class="hero'))
        self.assertLess(h.index('class="hero'), h.index("titulo-novidades"))
        self.assertLess(h.index("id=\"titulo-novidades\""), h.index("id=\"titulo-contato\""))
