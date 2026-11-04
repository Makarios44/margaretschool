import shutil
import tempfile
from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Aluno, Responsavel

TMP_MEDIA = tempfile.mkdtemp()


def formset_data(prefix, rows):
    data = {
        f"{prefix}-TOTAL_FORMS": len(rows), f"{prefix}-INITIAL_FORMS": 0,
        f"{prefix}-MIN_NUM_FORMS": 1, f"{prefix}-MAX_NUM_FORMS": 1000,
    }
    for i, row in enumerate(rows):
        for k, v in row.items():
            data[f"{prefix}-{i}-{k}"] = v
    return data


def dados_aluno(**extra):
    data = {"nome": "Maria Clara", "data_nascimento": "2022-03-10", "alergias": "Amendoim"}
    data.update(formset_data("resp", [{
        "nome": "Joana Silva", "parentesco": "mae", "telefone": "84 99999-0000",
        "responsavel_legal": "on", "responsavel_financeiro": "on",
    }]))
    data.update(formset_data("cont", [{
        "nome": "Rita", "parentesco": "tia", "telefone": "84 98888-0000",
    }]))
    data.update(extra)
    return data


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class AlunoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user("sec", password="x", is_staff=True)
        self.pai = U.objects.create_user("pai", password="x")

    def test_acesso(self):
        r = self.client.get(reverse("aluno_list"))
        self.assertEqual(r.status_code, 302)
        self.client.force_login(self.pai)
        self.assertEqual(self.client.get(reverse("aluno_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("aluno_create")).status_code, 403)

    def test_cadastro_completo_com_foto(self):
        self.client.force_login(self.staff)
        buf = BytesIO()
        Image.new("RGB", (20, 20), "red").save(buf, "PNG")
        foto = SimpleUploadedFile("f.png", buf.getvalue(), content_type="image/png")
        r = self.client.post(reverse("aluno_create"), dados_aluno(foto=foto))
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        a = Aluno.objects.get()
        self.assertTrue(a.foto)
        self.assertEqual(a.responsaveis.count(), 1)
        self.assertEqual(a.contatos_emergencia.count(), 1)
        self.assertContains(self.client.get(reverse("aluno_detail", args=[a.pk])), "Amendoim")

    def test_exige_responsavel_e_contato(self):
        self.client.force_login(self.staff)
        data = dados_aluno()
        data.update(formset_data("resp", []))
        r = self.client.post(reverse("aluno_create"), data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Informe ao menos um responsável.")
        self.assertEqual(Aluno.objects.count(), 0)

    def test_nascimento_no_futuro(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse("aluno_create"), dados_aluno(data_nascimento="2999-01-01"))
        self.assertContains(r, "não pode ser no futuro")

    def test_idade(self):
        hoje = date.today()
        a = Aluno(nome="x", data_nascimento=date(hoje.year - 3, hoje.month, 1))
        self.assertTrue(a.idade.startswith("3 anos"))


class BuscaAlunoTests(TestCase):
    """Campo de aluno por digitação (usado em Nova matrícula)."""

    def setUp(self):
        from decimal import Decimal as D
        from matriculas.models import AnoLetivo, Matricula, Turma

        U = get_user_model()
        self.staff = U.objects.create_user("sec", password="x", is_staff=True)
        self.pai = U.objects.create_user("pai", password="x")
        self.client.force_login(self.staff)
        self.ano = AnoLetivo.objects.create(ano=2026, atual=True)
        self.turma = Turma.objects.create(nome="Jardim II", ano_letivo=self.ano, turno="manha")
        self.maria1 = Aluno.objects.create(nome="Maria Clara Souza", data_nascimento=date(2021, 3, 4))
        self.maria2 = Aluno.objects.create(nome="Maria Clara Souza", data_nascimento=date(2022, 8, 9))
        self.jose = Aluno.objects.create(nome="José Antônio Lima", data_nascimento=date(2020, 1, 1))
        Responsavel.objects.create(aluno=self.maria1, nome="Paula Souza", parentesco="mae", telefone="1",
                                   responsavel_financeiro=True)
        Responsavel.objects.create(aluno=self.maria2, nome="Carla Souza", parentesco="mae", telefone="2",
                                   responsavel_financeiro=True)
        from matriculas.models import Matricula
        Matricula.objects.create(aluno=self.maria1, ano_letivo=self.ano, turma=self.turma, mensalidade=D("500"))

    def buscar(self, q):
        r = self.client.get(reverse("aluno_buscar"), {"q": q})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_lista_diminui_conforme_digita(self):
        self.assertEqual(self.buscar("m")["resultados"], [])  # menos de 2 letras: nada
        self.assertEqual(self.buscar("ma")["total"], 3)  # "Lima" também tem "ma"
        self.assertEqual(self.buscar("mar")["total"], 2)
        self.assertEqual(self.buscar("maria cl")["total"], 2)
        self.assertEqual(self.buscar("jo")["total"], 1)
        self.assertEqual(self.buscar("zzz")["total"], 0)

    def test_ignora_acentos_maiusculas_e_ordem_das_palavras(self):
        for texto in ("jose", "JOSÉ", "antonio jose", "  jose   lima "):
            r = self.buscar(texto)
            self.assertEqual([a["nome"] for a in r["resultados"]], ["José Antônio Lima"], texto)

    def test_homonimos_se_distinguem_por_nascimento_responsavel_e_turma(self):
        r = self.buscar("maria clara souza")["resultados"]
        self.assertEqual(len(r), 2)
        detalhes = {a["id"]: a["detalhe"] for a in r}
        self.assertIn("04/03/2021", detalhes[self.maria1.pk])
        self.assertIn("Paula Souza", detalhes[self.maria1.pk])
        self.assertIn("Jardim II", detalhes[self.maria1.pk])
        self.assertIn("09/08/2022", detalhes[self.maria2.pk])
        self.assertIn("Carla Souza", detalhes[self.maria2.pk])
        self.assertNotIn("Jardim", detalhes[self.maria2.pk])

    def test_limite_de_dez_resultados_com_total(self):
        for i in range(12):
            Aluno.objects.create(nome=f"Pedro {i:02d}", data_nascimento=date(2020, 1, 1))
        r = self.buscar("pedro")
        self.assertEqual((len(r["resultados"]), r["total"]), (10, 12))

    def test_nome_busca_acompanha_edicoes(self):
        self.jose.nome = "Zé Ântonio"
        self.jose.save()
        self.assertEqual(self.buscar("ze ant")["total"], 1)
        self.assertEqual(self.buscar("jose")["total"], 0)

    def test_somente_equipe(self):
        self.client.force_login(self.pai)
        self.assertEqual(self.client.get(reverse("aluno_buscar"), {"q": "maria"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("aluno_buscar"), {"q": "maria"}).status_code, 302)

    def test_formulario_de_matricula_usa_o_campo_de_busca(self):
        r = self.client.get(reverse("matricula_create"))
        self.assertContains(r, "data-aluno-autocomplete")
        self.assertContains(r, reverse("aluno_buscar"))
        self.assertNotContains(r, "<select name=\"aluno\"")
        pre = self.client.get(reverse("matricula_create") + f"?aluno={self.jose.pk}")
        self.assertContains(pre, "José Antônio Lima")  # vem já escolhido
        dados = {"aluno": self.jose.pk, "ano_letivo": self.ano.pk, "turma": self.turma.pk, "tipo": "nova",
                 "data_matricula": "2026-02-01", "situacao": "ativo", "taxa_matricula": "0",
                 "mensalidade": "500", "dia_vencimento": 10}
        from matriculas.models import Matricula
        ok = self.client.post(reverse("matricula_create"), dados)
        self.assertEqual(ok.status_code, 302)
        self.assertTrue(Matricula.objects.filter(aluno=self.jose).exists())
        sem = self.client.post(reverse("matricula_create"), {**dados, "aluno": ""})
        self.assertContains(sem, "Escolha o aluno na lista")

    def test_matricula_em_edicao_mostra_aluno_sem_busca(self):
        from matriculas.models import Matricula
        m = Matricula.objects.get(aluno=self.maria1)
        r = self.client.get(reverse("matricula_update", args=[m.pk]))
        self.assertContains(r, "Maria Clara Souza")
        self.assertNotContains(r, 'role="combobox"')
