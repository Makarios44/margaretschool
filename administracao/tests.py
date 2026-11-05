from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from alunos.models import Aluno
from documentos.models import DocumentoEmitido
from financeiro.models import CategoriaDespesa, Cobranca, Despesa
from matriculas.models import AnoLetivo, Matricula, Turma

from . import configuracao
from .models import ConfiguracaoEscola

User = get_user_model()
ESCOLA = {"nome": "Escola Padrão", "cnpj": "", "inep": "", "mantenedora": "", "endereco": "", "cidade": "Natal/RN",
          "telefone": "", "ato_autorizacao": "", "diretor": "Diretor do Arquivo", "diretor_ato": "",
          "secretario": "", "secretario_ato": ""}


class Base(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm", password="Senha-forte-123")
        self.sec = User.objects.create_user("sec", password="x", is_staff=True)
        self.pai = User.objects.create_user("pai", password="x")
        self.client.force_login(self.admin)


class AcessoTests(Base):
    def test_perfis(self):
        livres_para_equipe = ["administracao", "adm_anos", "adm_turmas", "adm_categorias"]
        so_admin = ["adm_escola", "adm_usuarios", "adm_usuario_novo"]
        self.client.force_login(self.sec)
        for nome in livres_para_equipe:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)
        for nome in so_admin:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 403, nome)
        self.client.force_login(self.pai)
        for nome in livres_para_equipe + so_admin:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 403, nome)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("administracao")).status_code, 302)

    def test_painel_nao_aponta_mais_para_o_admin_do_django(self):
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, reverse("administracao"))
        self.assertNotContains(r, 'href="/admin/')


@override_settings(ESCOLA=ESCOLA, FINANCEIRO={"multa_percentual": D("2"), "juros_mensal_percentual": D("1")},
                   CALENDARIO={"uf": "RN", "municipio": "Natal"})
class DadosDaEscolaTests(Base):
    def test_sem_configuracao_usa_o_padrao_do_arquivo(self):
        self.assertEqual(configuracao.escola()["diretor"], "Diretor do Arquivo")
        self.assertEqual(configuracao.financeiro()["multa_percentual"], D("2"))
        self.assertEqual(configuracao.calendario()["municipio"], "Natal")

    def test_tela_salva_e_sobrescreve_so_o_que_foi_preenchido(self):
        r = self.client.post(reverse("adm_escola"), {
            "nome": "", "cnpj": "12.345.678/0001-90", "diretor": "Maria Nova", "multa_percentual": "0",
            "juros_mensal_percentual": "", "calendario_uf": "rn", "calendario_municipio": "Mossoró"})
        self.assertEqual(r.status_code, 302)
        e = configuracao.escola()
        self.assertEqual((e["nome"], e["cnpj"], e["diretor"]), ("Escola Padrão", "12.345.678/0001-90", "Maria Nova"))
        f = configuracao.financeiro()
        self.assertEqual((f["multa_percentual"], f["juros_mensal_percentual"]), (D("0"), D("1")))  # 0 vale; vazio = padrão
        self.assertEqual(configuracao.calendario(), {"uf": "RN", "municipio": "Mossoró"})

    def test_valores_invalidos(self):
        r = self.client.post(reverse("adm_escola"), {"multa_percentual": "150"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ConfiguracaoEscola.objects.exists())

    def test_documentos_e_multa_usam_a_configuracao_nova(self):
        ConfiguracaoEscola.objects.create(diretor="Direção da Tela", multa_percentual=D("0"), juros_mensal_percentual=D("0"))
        ano = AnoLetivo.objects.create(ano=date.today().year, atual=True)
        turma = Turma.objects.create(nome="J", ano_letivo=ano, turno="manha")
        aluno = Aluno.objects.create(nome="Ana", data_nascimento=date(2020, 1, 1))
        m = Matricula.objects.create(aluno=aluno, ano_letivo=ano, turma=turma, mensalidade=D("600"))
        r = self.client.post(reverse("documento_form", args=["declaracao-matricula", aluno.pk]),
                             {"matricula": m.pk, "finalidade": ""})
        doc = DocumentoEmitido.objects.get()
        self.assertEqual(doc.conteudo["escola"]["diretor"], "Direção da Tela")
        self.assertContains(self.client.get(reverse("documento_ver", args=[doc.pk])), "Direção da Tela")
        c = Cobranca.objects.create(matricula=m, tipo="avulsa", descricao="x", valor=D("600"),
                                    vencimento=date.today().replace(year=date.today().year - 1))
        self.assertEqual(c.calcular_encargos(), (D("0.00"), D("0.00")))  # multa e juros zerados na tela

    def test_leitura_unica_por_requisicao(self):
        ConfiguracaoEscola.objects.create(diretor="A")
        with self.assertNumQueries(1):
            configuracao.iniciar_requisicao()
            try:
                configuracao.escola(); configuracao.financeiro(); configuracao.calendario()
            finally:
                configuracao.encerrar_requisicao()
        # fora de requisição não guarda nada: mudanças aparecem na hora
        ConfiguracaoEscola.objects.update(diretor="B")
        self.assertEqual(configuracao.escola()["diretor"], "B")


class AnosETurmasTests(Base):
    def test_criar_editar_e_excluir_ano(self):
        self.assertEqual(self.client.post(reverse("adm_ano_novo"), {"ano": 2027, "atual": "on"}).status_code, 302)
        ano = AnoLetivo.objects.get(ano=2027)
        self.assertTrue(ano.atual)
        dup = self.client.post(reverse("adm_ano_novo"), {"ano": 2027})
        self.assertEqual(dup.status_code, 200)
        self.assertContains(self.client.post(reverse("adm_ano_novo"), {"ano": 1999}), "entre 2000 e 2100")
        self.client.post(reverse("adm_ano_editar", args=[ano.pk]), {"ano": 2027})
        ano.refresh_from_db()
        self.assertFalse(ano.atual)
        self.assertContains(self.client.get(reverse("adm_anos")), "Não configurado")
        self.client.post(reverse("adm_ano_excluir", args=[ano.pk]))
        self.assertFalse(AnoLetivo.objects.exists())

    def test_ano_com_turma_nao_exclui(self):
        ano = AnoLetivo.objects.create(ano=2026)
        Turma.objects.create(nome="J", ano_letivo=ano, turno="manha")
        self.client.post(reverse("adm_ano_excluir", args=[ano.pk]))
        self.assertTrue(AnoLetivo.objects.filter(pk=ano.pk).exists())

    def test_turmas_crud_filtro_e_protecao(self):
        a26, a27 = AnoLetivo.objects.create(ano=2026), AnoLetivo.objects.create(ano=2027, atual=True)
        r = self.client.post(reverse("adm_turma_nova"), {"nome": "Maternal II", "ano_letivo": a27.pk, "turno": "tarde",
                                                         "etapa": "infantil_creche", "vagas": 12})
        self.assertEqual(r.status_code, 302)
        t = Turma.objects.get()
        self.assertEqual((t.etapa, t.vagas, t.turno), ("infantil_creche", 12, "tarde"))
        self.assertContains(self.client.get(reverse("adm_turmas")), "Maternal II")  # ano atual por padrão
        self.assertNotContains(self.client.get(reverse("adm_turmas") + f"?ano={a26.pk}"), "Maternal II")
        aluno = Aluno.objects.create(nome="Ana", data_nascimento=date(2022, 1, 1))
        Matricula.objects.create(aluno=aluno, ano_letivo=a27, turma=t, mensalidade=D("500"))
        self.client.post(reverse("adm_turma_excluir", args=[t.pk]))
        self.assertTrue(Turma.objects.filter(pk=t.pk).exists())

    def test_copiar_turmas_de_um_ano_para_outro(self):
        a26, a27 = AnoLetivo.objects.create(ano=2026), AnoLetivo.objects.create(ano=2027)
        Turma.objects.create(nome="Jardim I", ano_letivo=a26, turno="manha", etapa="infantil_pre", vagas=15)
        Turma.objects.create(nome="1º Ano", ano_letivo=a26, turno="tarde", etapa="fundamental_iniciais")
        dados = {"origem": a26.pk, "destino": a27.pk}
        self.client.post(reverse("adm_turmas_copiar"), dados)
        novas = Turma.objects.filter(ano_letivo=a27)
        self.assertEqual(novas.count(), 2)
        j = novas.get(nome="Jardim I")
        self.assertEqual((j.etapa, j.vagas, j.turno), ("infantil_pre", 15, "manha"))
        self.client.post(reverse("adm_turmas_copiar"), dados)  # repetir não duplica
        self.assertEqual(Turma.objects.filter(ano_letivo=a27).count(), 2)
        self.client.post(reverse("adm_turmas_copiar"), {"origem": a26.pk, "destino": a26.pk})
        self.assertEqual(Turma.objects.filter(ano_letivo=a26).count(), 2)

    def test_telas_mandam_cadastrar_ano_sem_usar_o_admin_do_django(self):
        r = self.client.get(reverse("rematricula_list"))
        self.assertContains(r, reverse("adm_ano_novo"))
        self.assertNotContains(r, "/admin/")


class UsuariosTests(Base):
    def dados(self, **kw):
        d = {"username": "ana", "first_name": "Ana", "last_name": "Silva", "email": "a@x.com",
             "perfil": "secretaria", "password1": "Senha-boa-9876", "password2": "Senha-boa-9876"}
        d.update(kw)
        return d

    def test_criar_com_cada_perfil(self):
        for perfil, staff, superu in [("familia", False, False), ("secretaria", True, False), ("admin", True, True)]:
            r = self.client.post(reverse("adm_usuario_novo"), self.dados(username=f"u_{perfil}", perfil=perfil, email=f"{perfil}@x.com"))
            self.assertEqual(r.status_code, 302, perfil)
            u = User.objects.get(username=f"u_{perfil}")
            self.assertEqual((u.is_staff, u.is_superuser, u.is_active), (staff, superu, True))
            self.assertTrue(u.check_password("Senha-boa-9876"))

    def test_senha_fraca_ou_diferente(self):
        self.assertContains(self.client.post(reverse("adm_usuario_novo"), self.dados(password2="outra")), "não são iguais")
        r = self.client.post(reverse("adm_usuario_novo"), self.dados(password1="12345678", password2="12345678"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="ana").exists())

    def test_editar_perfil_e_proteger_o_proprio_acesso(self):
        u = User.objects.create_user("bia", password="x", is_staff=True)
        self.client.post(reverse("adm_usuario_editar", args=[u.pk]),
                         {"username": "bia", "first_name": "Bia", "perfil": "familia"})
        u.refresh_from_db()
        self.assertEqual((u.is_staff, u.first_name), (False, "Bia"))
        # o administrador não pode se rebaixar nem se desativar
        r = self.client.post(reverse("adm_usuario_editar", args=[self.admin.pk]), {"username": "adm", "perfil": "secretaria"})
        self.assertContains(r, "seu próprio acesso")
        self.client.post(reverse("adm_usuario_ativo", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active and self.admin.is_superuser)

    def test_ultimo_administrador_nao_e_rebaixado_nem_desativado_por_outro(self):
        outro = User.objects.create_superuser("adm2", password="x")
        self.client.force_login(outro)
        self.client.post(reverse("adm_usuario_ativo", args=[self.admin.pk]))  # há 2 admins: pode
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)
        # agora "outro" é o único ativo; o próprio sistema não deixa desativar
        self.client.post(reverse("adm_usuario_ativo", args=[outro.pk]))
        outro.refresh_from_db()
        self.assertTrue(outro.is_active)

    def test_desativar_reativar_e_login(self):
        u = User.objects.create_user("carlos", password="Senha-boa-9876", is_staff=True)
        self.client.post(reverse("adm_usuario_ativo", args=[u.pk]))
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertFalse(self.client.__class__().login(username="carlos", password="Senha-boa-9876"))
        self.client.post(reverse("adm_usuario_ativo", args=[u.pk]))
        u.refresh_from_db()
        self.assertTrue(u.is_active)

    def test_redefinir_senha(self):
        u = User.objects.create_user("dora", password="antiga-123456")
        r = self.client.post(reverse("adm_usuario_senha", args=[u.pk]), {"password1": "Nova-senha-4321", "password2": "Nova-senha-4321"})
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.check_password("Nova-senha-4321"))
        fraca = self.client.post(reverse("adm_usuario_senha", args=[u.pk]), {"password1": "123", "password2": "123"})
        self.assertEqual(fraca.status_code, 200)
        self.assertTrue(User.objects.get(pk=u.pk).check_password("Nova-senha-4321"))

    def test_lista_mostra_perfis(self):
        r = self.client.get(reverse("adm_usuarios"))
        self.assertContains(r, "Administrador")
        self.assertContains(r, "Secretaria")
        self.assertContains(r, "Família / professor")


class CategoriasTests(Base):
    def test_categorias_iniciais_existem(self):
        self.assertTrue(CategoriaDespesa.objects.filter(nome="Material didático e livros").exists())
        self.assertGreaterEqual(CategoriaDespesa.objects.count(), 14)

    def test_criar_desativar_e_excluir(self):
        self.client.post(reverse("adm_categoria_nova"), {"nome": "Uniformes", "ativa": "on"})
        c = CategoriaDespesa.objects.get(nome="Uniformes")
        self.assertContains(self.client.post(reverse("adm_categoria_nova"), {"nome": "Uniformes"}), "já existe")
        self.client.post(reverse("adm_categoria_ativa", args=[c.pk]))
        c.refresh_from_db()
        self.assertFalse(c.ativa)
        Despesa.objects.create(data=date.today(), descricao="x", categoria=c, valor=D("10"), forma_pagamento="pix")
        self.client.post(reverse("adm_categoria_excluir", args=[c.pk]))
        self.assertTrue(CategoriaDespesa.objects.filter(pk=c.pk).exists())  # já usada: só desativa
        livre = CategoriaDespesa.objects.create(nome="Livre")
        self.client.post(reverse("adm_categoria_excluir", args=[livre.pk]))
        self.assertFalse(CategoriaDespesa.objects.filter(pk=livre.pk).exists())
