import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


class MidiaTests(TestCase):
    """Uploads em media/: banners públicos, o resto só para a equipe."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        for rel in ("anuncios/2026/banner.jpg", "alunos/fotos/crianca.jpg", "despesas/2026/nota.pdf"):
            caminho = os.path.join(self.pasta, rel)
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            with open(caminho, "wb") as f:
                f.write(b"conteudo")
        override = override_settings(MEDIA_ROOT=self.pasta)
        override.enable()
        self.addCleanup(override.disable)
        U = get_user_model()
        self.staff = U.objects.create_user("sec", password="x", is_staff=True)
        self.comum = U.objects.create_user("comum", password="x")

    def test_banner_e_publico(self):
        r = self.client.get("/media/anuncios/2026/banner.jpg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "public, max-age=86400")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

    def test_foto_de_aluno_e_comprovante_so_para_equipe(self):
        privados = ("/media/alunos/fotos/crianca.jpg", "/media/despesas/2026/nota.pdf")
        for usuario in (None, self.comum):
            if usuario:
                self.client.force_login(usuario)
            for url in privados:
                self.assertEqual(self.client.get(url).status_code, 404, url)
        self.client.force_login(self.staff)
        for url in privados:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertEqual(r["Cache-Control"], "private, no-store")

    def test_nao_sai_da_pasta(self):
        self.client.force_login(self.staff)
        for url in ("/media/../config/settings.py", "/media/anuncios/../../manage.py"):
            self.assertIn(self.client.get(url).status_code, (400, 404), url)  # Django recusa o "../"
        self.assertEqual(self.client.get("/media/inexistente.jpg").status_code, 404)


class TutorialTests(TestCase):
    """Tutorial de boas-vindas: aparece no primeiro acesso e fica sempre disponível em /ajuda/."""

    def setUp(self):
        U = get_user_model()
        self.familia = U.objects.create_user("fam", password="x", first_name="Dona Rita")
        self.sec = U.objects.create_user("sec2", password="x", is_staff=True)
        self.adm = U.objects.create_user("adm", password="x", is_staff=True, is_superuser=True)

    def entrar(self, usuario, **extra):
        return self.client.post("/entrar/", {"username": usuario, "password": "x", **extra})

    def test_primeiro_login_vai_ao_tutorial(self):
        r = self.entrar("fam")
        self.assertRedirects(r, "/ajuda/?primeira=1", fetch_redirect_response=False)
        pagina = self.client.get("/ajuda/", {"primeira": 1})
        self.assertContains(pagina, "Bem-vindo(a), Dona Rita!")
        self.assertContains(pagina, "Concluir e ir para o painel")
        self.assertContains(pagina, "Pular o tutorial")

    def test_concluir_marca_como_visto_e_nao_aparece_mais(self):
        from .models import TutorialVisto
        self.entrar("fam")
        r = self.client.post("/ajuda/concluir/")
        self.assertRedirects(r, "/painel/", fetch_redirect_response=False)
        self.assertTrue(TutorialVisto.objects.filter(usuario=self.familia).exists())
        self.client.post("/sair/")
        self.assertRedirects(self.entrar("fam"), "/painel/", fetch_redirect_response=False)
        # depois de visto, ?primeira=1 não reabre o modo boas-vindas, mas a página continua acessível
        pagina = self.client.get("/ajuda/", {"primeira": 1})
        self.assertContains(pagina, "Como usar o sistema")
        self.assertNotContains(pagina, "Pular o tutorial")

    def test_sem_concluir_volta_a_aparecer_no_proximo_login(self):
        self.entrar("fam")
        self.client.post("/sair/")
        self.assertRedirects(self.entrar("fam"), "/ajuda/?primeira=1", fetch_redirect_response=False)

    def test_login_com_next_respeita_o_destino(self):
        r = self.entrar("fam", next="/calendario/")
        self.assertRedirects(r, "/calendario/", fetch_redirect_response=False)

    def test_concluir_exige_post_e_login(self):
        self.assertEqual(self.client.get("/ajuda/concluir/").status_code, 302)  # sem login -> entrar
        self.client.force_login(self.familia)
        self.assertEqual(self.client.get("/ajuda/concluir/").status_code, 405)

    def test_ajuda_exige_login(self):
        r = self.client.get("/ajuda/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/entrar/", r["Location"])

    def test_conteudo_por_perfil(self):
        self.client.force_login(self.familia)
        r = self.client.get("/ajuda/")
        self.assertContains(r, "Calendário da escola")
        self.assertNotContains(r, "Chamada de todo dia")
        self.assertNotContains(r, "Administração</h2>")
        self.client.force_login(self.sec)
        r = self.client.get("/ajuda/")
        self.assertContains(r, "Chamada de todo dia")
        self.assertContains(r, "Financeiro")
        self.assertNotContains(r, "Cadastre o ano letivo")
        self.client.force_login(self.adm)
        self.assertContains(self.client.get("/ajuda/"), "Cadastre o ano letivo")

    def test_botoes_destacados_e_html_escapado(self):
        from .templatetags.ajuda import botoes
        self.assertEqual(str(botoes("Toque em [Menu]")), 'Toque em <span class="tecla">Menu</span>')
        self.assertNotIn("<script>", str(botoes("[<script>x</script>]")))

    def test_link_ajuda_no_menu_e_no_painel(self):
        self.client.force_login(self.familia)
        r = self.client.get("/painel/")
        self.assertContains(r, 'href="/ajuda/"')
        self.assertContains(r, "Abrir o tutorial")
        self.client.logout()
        self.assertNotContains(self.client.get("/"), 'href="/ajuda/"')
