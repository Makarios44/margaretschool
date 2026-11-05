import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()
LOCMEM = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}


@override_settings(**LOCMEM)
class RecuperacaoDeSenhaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.u = User.objects.create_user("ana", "ana@exemplo.com", "SenhaAntiga#123", first_name="Ana")

    def pedir(self, email):
        return self.client.post(reverse("password_reset"), {"email": email})

    def link(self):
        return re.search(r"https?://\S+/senha/nova/\S+/", mail.outbox[-1].body).group(0)

    def test_login_tem_link(self):
        self.assertContains(self.client.get(reverse("login")), reverse("password_reset"))

    def test_fluxo_completo(self):
        r = self.pedir("ana@exemplo.com")
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ana", mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].alternatives)
        url = "/" + self.link().split("/", 3)[3]
        r = self.client.get(url, follow=True)
        self.assertContains(r, "Criar nova senha")
        post_url = r.redirect_chain[-1][0]
        r = self.client.post(post_url, {"new_password1": "OutraSenha#987x", "new_password2": "OutraSenha#987x"})
        self.assertRedirects(r, reverse("password_reset_complete"))
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("OutraSenha#987x"))
        # link não funciona de novo
        self.assertContains(self.client.get(url, follow=True), "Link vencido")

    def test_email_desconhecido_responde_igual_e_nao_envia(self):
        r = self.pedir("ninguem@exemplo.com")
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_usuario_inativo_nao_recebe(self):
        self.u.is_active = False
        self.u.save()
        self.pedir("ana@exemplo.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_limite_de_um_pedido_por_minuto(self):
        self.pedir("ana@exemplo.com")
        self.pedir("ANA@exemplo.com")
        self.assertEqual(len(mail.outbox), 1)

    def test_senha_fraca_recusada(self):
        self.pedir("ana@exemplo.com")
        url = "/" + self.link().split("/", 3)[3]
        post_url = self.client.get(url, follow=True).redirect_chain[-1][0]
        r = self.client.post(post_url, {"new_password1": "12345678", "new_password2": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("SenhaAntiga#123"))

    def test_token_invalido(self):
        self.assertContains(self.client.get("/senha/nova/abc/def/"), "Link vencido")


@override_settings(**LOCMEM)
class ConviteETesteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.adm = User.objects.create_superuser("adm", "adm@exemplo.com", "Admin#12345x")
        self.client.force_login(self.adm)

    def dados(self, **extra):
        d = {"username": "bia", "first_name": "Bia", "last_name": "Souza", "email": "bia@exemplo.com",
             "perfil": "secretaria", "enviar_convite": "on"}
        d.update(extra)
        return d

    def test_convite_cria_usuario_sem_senha_e_envia(self):
        r = self.client.post(reverse("adm_usuario_novo"), self.dados())
        self.assertRedirects(r, reverse("adm_usuarios"))
        u = User.objects.get(username="bia")
        self.assertFalse(u.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bia@exemplo.com"])
        self.assertIn("Criar minha senha", mail.outbox[0].alternatives[0][0])

    def test_convite_exige_email(self):
        r = self.client.post(reverse("adm_usuario_novo"), self.dados(email=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="bia").exists())

    def test_sem_convite_exige_senha(self):
        r = self.client.post(reverse("adm_usuario_novo"), self.dados(enviar_convite=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="bia").exists())

    def test_criar_com_senha_continua_funcionando(self):
        r = self.client.post(reverse("adm_usuario_novo"), self.dados(
            enviar_convite="", password1="Senha#Forte987", password2="Senha#Forte987"))
        self.assertRedirects(r, reverse("adm_usuarios"))
        self.assertTrue(User.objects.get(username="bia").check_password("Senha#Forte987"))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_duplicado(self):
        r = self.client.post(reverse("adm_usuario_novo"), self.dados(email="ADM@exemplo.com"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Já existe um usuário com este e-mail")

    def test_enviar_link_na_lista(self):
        u = User.objects.create_user("caio", "caio@exemplo.com", "x")
        r = self.client.post(reverse("adm_usuario_link", args=[u.pk]))
        self.assertRedirects(r, reverse("adm_usuarios"))
        self.assertEqual(len(mail.outbox), 1)

    def test_falha_no_envio_nao_derruba(self):
        with override_settings(EMAIL_BACKEND="nao.existe.Backend"):
            r = self.client.post(reverse("adm_usuario_novo"), self.dados())
        self.assertRedirects(r, reverse("adm_usuarios"))
        self.assertTrue(User.objects.filter(username="bia").exists())

    def test_pagina_de_email_so_admin(self):
        self.assertEqual(self.client.get(reverse("adm_email")).status_code, 200)
        sec = User.objects.create_user("sec", "sec@exemplo.com", "x", is_staff=True)
        self.client.force_login(sec)
        self.assertNotEqual(self.client.get(reverse("adm_email")).status_code, 200)

    def test_email_de_teste(self):
        self.client.post(reverse("adm_email"), {"destino": "dest@exemplo.com"})
        self.assertEqual(mail.outbox[0].to, ["dest@exemplo.com"])
