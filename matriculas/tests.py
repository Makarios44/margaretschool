from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alunos.models import Aluno, ContatoEmergencia, Responsavel

from .models import AnoLetivo, Matricula, Turma


class MatriculaTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("sec", password="x", is_staff=True)
        self.client.force_login(self.staff)
        self.a25 = AnoLetivo.objects.create(ano=2025)
        self.a26 = AnoLetivo.objects.create(ano=2026, atual=True)
        self.t25 = Turma.objects.create(nome="Maternal I", ano_letivo=self.a25, turno="manha")
        self.t26 = Turma.objects.create(nome="Maternal II", ano_letivo=self.a26, turno="tarde")
        self.aluno = Aluno.objects.create(nome="Pedro Lima", data_nascimento=date(2022, 5, 1))
        Responsavel.objects.create(
            aluno=self.aluno, nome="Ana Lima", parentesco="mae", telefone="1",
            responsavel_financeiro=True,
        )
        ContatoEmergencia.objects.create(aluno=self.aluno, nome="Rita", parentesco="tia", telefone="2")

    def dados(self, **kw):
        d = {
            "aluno": self.aluno.pk, "ano_letivo": self.a25.pk, "turma": self.t25.pk,
            "tipo": "nova", "data_matricula": "2025-01-15", "situacao": "ativo",
            "taxa_matricula": "150.00", "mensalidade": "600.00", "dia_vencimento": 10,
        }
        d.update(kw)
        return d

    def test_ano_atual_unico(self):
        AnoLetivo.objects.create(ano=2027, atual=True)
        self.assertEqual(AnoLetivo.objects.filter(atual=True).count(), 1)

    def test_criar_matricula_gera_documentos_e_turno(self):
        r = self.client.post(reverse("matricula_create"), self.dados())
        self.assertEqual(r.status_code, 302)
        m = Matricula.objects.get()
        self.assertEqual(m.turno, "manha")
        self.assertEqual(m.documentos.count(), 5)
        self.assertEqual(m.docs_pendentes, 5)

    def test_turma_de_outro_ano_e_duplicidade(self):
        r = self.client.post(reverse("matricula_create"), self.dados(turma=self.t26.pk))
        self.assertContains(r, "pertence a outro ano letivo")
        self.client.post(reverse("matricula_create"), self.dados())
        r = self.client.post(reverse("matricula_create"), self.dados())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Matricula.objects.count(), 1)

    def test_documentos_marcar_e_desmarcar(self):
        self.client.post(reverse("matricula_create"), self.dados())
        m = Matricula.objects.get()
        ids = list(m.documentos.values_list("pk", flat=True))[:2]
        self.client.post(reverse("matricula_documentos", args=[m.pk]), {"entregue": ids})
        self.assertEqual(m.docs_pendentes, 3)
        self.assertIsNotNone(m.documentos.get(pk=ids[0]).data_entrega)
        self.client.post(reverse("matricula_documentos", args=[m.pk]), {})
        self.assertEqual(m.docs_pendentes, 5)

    def test_rematricula(self):
        self.client.post(reverse("matricula_create"), self.dados())
        r = self.client.get(reverse("rematricula_list") + f"?ano={self.a26.pk}")
        self.assertContains(r, "Pedro Lima")
        url = reverse("matricula_create") + f"?aluno={self.aluno.pk}&ano={self.a26.pk}&tipo=rematricula"
        r = self.client.get(url)
        self.assertEqual(r.context["form"].initial["mensalidade"], 600)
        self.assertEqual(r.context["form"].initial["tipo"], "rematricula")
        self.client.post(reverse("matricula_create"), self.dados(
            ano_letivo=self.a26.pk, turma=self.t26.pk, tipo="rematricula"))
        r = self.client.get(reverse("rematricula_list") + f"?ano={self.a26.pk}")
        self.assertNotContains(r, "Pedro Lima")
        self.assertEqual(self.aluno.matricula_atual.ano_letivo, self.a26)

    def test_impressao(self):
        self.client.post(reverse("matricula_create"), self.dados())
        m = Matricula.objects.get()
        ficha = self.client.get(reverse("matricula_ficha", args=[m.pk]))
        self.assertContains(ficha, "Pedro Lima")
        self.assertContains(ficha, "Cartão de vacinação")
        contrato = self.client.get(reverse("matricula_contrato", args=[m.pk]))
        self.assertContains(contrato, "Ana Lima")
        self.assertContains(contrato, "600,00")

    def test_filtros_e_listas(self):
        self.client.post(reverse("matricula_create"), self.dados())
        sem = Aluno.objects.create(nome="Sem Turma", data_nascimento=date(2023, 1, 1))
        r = self.client.get(reverse("aluno_list") + "?situacao=sem")
        self.assertContains(r, sem.nome)
        self.assertNotContains(r, "Pedro Lima")
        r = self.client.get(reverse("aluno_list") + f"?ano={self.a25.pk}&situacao=ativo")
        self.assertContains(r, "Pedro Lima")
        self.assertNotContains(r, "Sem Turma")
        r = self.client.get(reverse("matricula_list") + "?ano=")
        self.assertContains(r, "Pedro Lima")
        r = self.client.get(reverse("matricula_list"))  # padrão = 2026, sem matrículas
        self.assertNotContains(r, "Pedro Lima")

    def test_somente_equipe(self):
        self.client.force_login(get_user_model().objects.create_user("pai", password="x"))
        for name in ["matricula_list", "rematricula_list", "matricula_create"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)


class DocumentoExtraTests(MatriculaTests):
    def test_acrescentar_documento_pela_tela_da_matricula(self):
        from .models import DocumentoMatricula

        self.client.post(reverse("matricula_create"), self.dados())
        m = Matricula.objects.get()
        url = reverse("matricula_documento_adicionar", args=[m.pk])
        self.assertContains(self.client.get(reverse("matricula_detail", args=[m.pk])), "Laudo ou relatório médico")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {"tipo": "laudo"})
        self.assertEqual(m.documentos.count(), 6)
        self.assertTrue(m.documentos.filter(tipo="laudo", entregue=False).exists())
        self.client.post(url, {"tipo": "laudo"})  # repetir não duplica
        self.client.post(url, {"tipo": "invalido"})
        self.assertEqual(m.documentos.count(), 6)
        self.assertNotContains(self.client.get(reverse("matricula_detail", args=[m.pk])), 'value="laudo">Laudo')
