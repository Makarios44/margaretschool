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
