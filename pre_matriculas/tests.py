from datetime import date, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alunos.models import Aluno, ContatoEmergencia, Responsavel
from financeiro.models import Cobranca
from matriculas.models import AnoLetivo, Matricula, Turma

from .models import LinkPreMatricula, SolicitacaoPreMatricula

Status = SolicitacaoPreMatricula.Status


class Base(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user("sec", password="x", is_staff=True)
        self.pai = U.objects.create_user("pai", password="x")
        self.ano = AnoLetivo.objects.create(ano=2027, atual=True)
        self.outro_ano = AnoLetivo.objects.create(ano=2026)
        self.turma = Turma.objects.create(nome="Jardim I", ano_letivo=self.ano, turno="manha", vagas=2)
        self.turma_antiga = Turma.objects.create(nome="Jardim I", ano_letivo=self.outro_ano, turno="manha")

    def novo_link(self, **kw):
        dados = dict(ano_letivo=self.ano, criado_por=self.staff)
        dados.update(kw)
        return LinkPreMatricula.objects.create(**dados)

    def dados(self, **kw):
        d = {
            "nome_crianca": "Helena Costa", "data_nascimento": "2023-04-10", "sexo": "F",
            "naturalidade": "Natal/RN", "certidao_nascimento": "123", "endereco": "Rua A, 1",
            "bairro": "Centro", "cidade": "Natal", "alergias": "Lactose",
            "nome_responsavel": "Paula Costa", "parentesco": "mae", "cpf_responsavel": "111.111.111-11",
            "telefone": "84 99999-0000", "email": "paula@example.com",
            "responsavel_legal": "on", "responsavel_financeiro": "on",
            "contato_emergencia_nome": "Rita Souza", "contato_emergencia_parentesco": "tia",
            "contato_emergencia_telefone": "84 98888-0000", "contato_pode_buscar": "on",
            "turma_desejada": self.turma.pk, "confirmar_dados": "on",
        }
        d.update(kw)
        return d

    def enviar(self, link=None, **kw):
        link = link or self.novo_link()
        r = self.client.post(reverse("pre_matricula_publica", args=[link.token]), self.dados(**kw))
        return link, r

    def solicitacao(self, **kw):
        link, r = self.enviar(**kw)
        erros = r.context["form"].errors if r.context and "form" in r.context else ""
        self.assertEqual(r.status_code, 200, erros)
        return SolicitacaoPreMatricula.objects.get(link=link)

    def aprovar(self, s, **kw):
        dados = {"turma": self.turma.pk, "mensalidade": "600.00", "taxa_matricula": "150.00",
                 "dia_vencimento": 10, "tipo": "nova"}
        dados.update(kw)
        self.client.force_login(self.staff)
        return self.client.post(reverse("pre_matricula_analisar", args=[s.pk]), dados)


class LinkTests(Base):
    def test_criar_link_so_equipe(self):
        url = reverse("pre_matricula_criar_link")
        self.client.force_login(self.pai)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"ano_letivo": self.ano.pk, "observacoes_internas": "família Costa"})
        link = LinkPreMatricula.objects.get()
        self.assertContains(r, f"/pre-matricula/{link.token}/")
        self.assertContains(r, "wa.me")
        self.assertEqual(link.criado_por, self.staff)
        self.assertTrue(link.valido)
        self.assertAlmostEqual((link.expira_em - timezone.now()).days, 13, delta=1)

    def test_situacao_do_link(self):
        self.assertEqual(self.novo_link().situacao, "aguardando")
        self.assertEqual(self.novo_link(ativo=False).situacao, "desativado")
        self.assertEqual(self.novo_link(usado_em=timezone.now()).situacao, "usado")
        self.assertEqual(self.novo_link(expira_em=timezone.now() - timedelta(minutes=1)).situacao, "expirado")

    def test_lista_e_desativar(self):
        link = self.novo_link(observacoes_internas="família Silva")
        self.client.force_login(self.staff)
        r = self.client.get(reverse("pre_matricula_links"))
        self.assertContains(r, "família Silva")
        self.assertContains(r, "Copiar")  # a equipe pode copiar de novo o link que aguarda a família
        self.assertContains(r, "Desativar")
        url = reverse("pre_matricula_desativar_link", args=[link.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        link.refresh_from_db()
        self.assertFalse(link.ativo)
        self.assertEqual(self.client.get(reverse("pre_matricula_publica", args=[link.token])).status_code, 410)
        depois = self.client.get(reverse("pre_matricula_links"))
        self.assertNotContains(depois, "Copiar")
        self.assertContains(depois, "Desativado")


class FormularioPublicoTests(Base):
    def test_abre_sem_login_e_so_turmas_do_ano_do_link(self):
        link = self.novo_link()
        r = self.client.get(reverse("pre_matricula_publica", args=[link.token]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Contato de emergência")
        self.assertEqual(list(r.context["form"].fields["turma_desejada"].queryset), [self.turma])

    def test_token_desconhecido_expirado_e_desativado(self):
        self.assertEqual(self.client.get(reverse("pre_matricula_publica", args=["nao-existe"])).status_code, 404)
        vencido = self.novo_link(expira_em=timezone.now() - timedelta(days=1))
        self.assertEqual(self.client.get(reverse("pre_matricula_publica", args=[vencido.token])).status_code, 410)
        off = self.novo_link(ativo=False)
        r = self.client.post(reverse("pre_matricula_publica", args=[off.token]), self.dados())
        self.assertEqual(r.status_code, 410)
        self.assertFalse(SolicitacaoPreMatricula.objects.exists())

    def test_envio_marca_link_como_usado_e_nao_aceita_segundo_envio(self):
        link, r = self.enviar()
        self.assertContains(r, "Pré-matrícula enviada")
        link.refresh_from_db()
        self.assertIsNotNone(link.usado_em)
        s = SolicitacaoPreMatricula.objects.get()
        self.assertEqual((s.status, s.nome_crianca, s.contato_emergencia_nome), (Status.RECEBIDA, "Helena Costa", "Rita Souza"))
        r2 = self.client.post(reverse("pre_matricula_publica", args=[link.token]), self.dados(nome_crianca="Outra"))
        self.assertEqual(r2.status_code, 410)
        self.assertEqual(SolicitacaoPreMatricula.objects.count(), 1)

    def test_validacoes_nao_gastam_o_link(self):
        link = self.novo_link()
        url = reverse("pre_matricula_publica", args=[link.token])
        casos = [
            ({"data_nascimento": "2999-01-01"}, "no futuro"),
            ({"contato_emergencia_nome": ""}, "obrigatório"),
            ({"confirmar_dados": ""}, "obrigatório"),
            ({"telefone": ""}, "obrigatório"),
        ]
        for kw, texto in casos:
            r = self.client.post(url, self.dados(**kw))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, texto)
        link.refresh_from_db()
        self.assertIsNone(link.usado_em)
        self.assertFalse(SolicitacaoPreMatricula.objects.exists())

    def test_turma_de_outro_ano_e_recusada(self):
        link = self.novo_link()
        r = self.client.post(reverse("pre_matricula_publica", args=[link.token]),
                             self.dados(turma_desejada=self.turma_antiga.pk))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SolicitacaoPreMatricula.objects.exists())


class AprovacaoTests(Base):
    def test_aprovar_cria_tudo(self):
        s = self.solicitacao()
        r = self.aprovar(s)
        s.refresh_from_db()
        self.assertEqual(s.status, Status.APROVADA)
        self.assertRedirects(r, reverse("matricula_detail", args=[s.matricula_criada.pk]))
        aluno = s.aluno_criado
        self.assertEqual((aluno.nome, aluno.naturalidade, aluno.alergias), ("Helena Costa", "Natal/RN", "Lactose"))
        resp = aluno.responsaveis.get()
        self.assertEqual((resp.nome, resp.parentesco, resp.responsavel_financeiro), ("Paula Costa", "mae", True))
        contato = aluno.contatos_emergencia.get()
        self.assertEqual((contato.nome, contato.telefone, contato.autorizado_buscar), ("Rita Souza", "84 98888-0000", True))
        m = s.matricula_criada
        self.assertEqual((m.situacao, m.mensalidade, m.taxa_matricula, m.turma, m.ano_letivo), ("ativo", D("600.00"), D("150.00"), self.turma, self.ano))
        self.assertFalse(m.taxa_paga)
        self.assertEqual(m.documentos.count(), 5)
        taxa = m.cobrancas.get()
        self.assertEqual((taxa.tipo, taxa.valor, taxa.situacao), ("taxa_matricula", D("150.00"), "aberta"))
        # a ficha do aluno já sai completa (responsável e contato de emergência)
        self.assertContains(self.client.get(reverse("ficha_individual", args=[aluno.pk])), "Rita Souza")

    def test_nao_duplica_taxa_ao_gerar_mensalidades(self):
        s = self.solicitacao()
        self.aprovar(s)
        s.refresh_from_db()
        r = self.client.get(reverse("gerar_mensalidades", args=[s.matricula_criada.pk]))
        self.assertNotContains(r, "Gerar também a taxa")

    def test_taxa_zero_nao_gera_cobranca(self):
        s = self.solicitacao()
        self.aprovar(s, taxa_matricula="0")
        self.assertFalse(Cobranca.objects.exists())

    def test_aprovada_vira_somente_leitura(self):
        s = self.solicitacao()
        self.aprovar(s)
        r = self.client.get(reverse("pre_matricula_analisar", args=[s.pk]))
        self.assertContains(r, "Pré-matrícula aprovada")
        self.assertNotContains(r, "Aprovar e criar matrícula")
        self.client.post(reverse("pre_matricula_analisar", args=[s.pk]), {"acao": "rejeitar"})
        s.refresh_from_db()
        self.assertEqual(s.status, Status.APROVADA)
        self.assertEqual(Aluno.objects.count(), 1)

    def test_turma_sem_vagas(self):
        for i in range(2):
            a = Aluno.objects.create(nome=f"Aluno {i}", data_nascimento=date(2022, 1, 1))
            Matricula.objects.create(aluno=a, ano_letivo=self.ano, turma=self.turma, mensalidade=D("500"))
        s = self.solicitacao()
        r = self.aprovar(s)
        self.assertContains(r, "não possui vagas")
        s.refresh_from_db()
        self.assertEqual(s.status, Status.RECEBIDA)
        self.assertEqual(Aluno.objects.filter(nome="Helena Costa").count(), 0)

    def test_turma_de_outro_ano_nao_aprova(self):
        s = self.solicitacao()
        r = self.aprovar(s, turma=self.turma_antiga.pk)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Aluno.objects.exists())

    def test_aluno_duplicado_pede_confirmacao(self):
        existente = Aluno.objects.create(nome="helena costa", data_nascimento=date(2023, 4, 10))
        Responsavel.objects.create(aluno=existente, nome="Antiga", parentesco="mae", telefone="1")
        s = self.solicitacao()
        self.client.force_login(self.staff)
        r = self.client.get(reverse("pre_matricula_analisar", args=[s.pk]))
        self.assertContains(r, "já existe um aluno")
        r = self.aprovar(s)  # sem marcar "usar cadastro existente"
        self.assertContains(r, "Já existe um aluno")
        self.assertEqual(Aluno.objects.count(), 1)
        self.assertFalse(Matricula.objects.exists())
        r = self.aprovar(s, usar_aluno_existente="on")
        s.refresh_from_db()
        self.assertEqual(s.status, Status.APROVADA)
        self.assertEqual(Aluno.objects.count(), 1)  # não criou outro aluno
        self.assertEqual(existente.responsaveis.count(), 1)  # nem outro responsável
        self.assertEqual(s.aluno_criado, existente)
        self.assertEqual(existente.matriculas.get().ano_letivo, self.ano)

    def test_aluno_existente_ja_matriculado_no_ano(self):
        existente = Aluno.objects.create(nome="Helena Costa", data_nascimento=date(2023, 4, 10))
        Matricula.objects.create(aluno=existente, ano_letivo=self.ano, turma=self.turma, mensalidade=D("500"))
        s = self.solicitacao()
        r = self.aprovar(s, usar_aluno_existente="on")
        self.assertContains(r, "já tem matrícula em 2027")
        self.assertEqual(existente.matriculas.count(), 1)

    def test_rejeitar_e_em_analise(self):
        s = self.solicitacao()
        self.client.force_login(self.staff)
        url = reverse("pre_matricula_analisar", args=[s.pk])
        self.client.post(url, {"acao": "em_analise"})
        s.refresh_from_db()
        self.assertEqual(s.status, Status.EM_ANALISE)
        self.client.post(url, {"acao": "rejeitar", "observacoes_secretaria": "Sem vaga"})
        s.refresh_from_db()
        self.assertEqual((s.status, s.observacoes_secretaria), (Status.REJEITADA, "Sem vaga"))
        self.assertFalse(Aluno.objects.exists())


class ListaEAcessoTests(Base):
    def test_lista_filtro_e_painel(self):
        s = self.solicitacao()
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("pre_matricula_lista")), "Helena Costa")
        self.assertContains(self.client.get(reverse("pre_matricula_lista") + "?status=aprovada"), "Nenhuma solicitação")
        painel = self.client.get(reverse("dashboard"))
        self.assertContains(painel, "1 para analisar")
        self.aprovar(s)
        self.assertNotContains(self.client.get(reverse("dashboard")), "para analisar")

    def test_somente_equipe(self):
        s = self.solicitacao()
        alvos = [("pre_matricula_lista", []), ("pre_matricula_links", []),
                 ("pre_matricula_criar_link", []), ("pre_matricula_analisar", [s.pk])]
        self.client.force_login(self.pai)
        for nome, args in alvos:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 403, nome)
        self.assertEqual(self.client.post(reverse("pre_matricula_analisar", args=[s.pk]), {"acao": "rejeitar"}).status_code, 403)
        self.client.logout()
        for nome, args in alvos:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 302, nome)
