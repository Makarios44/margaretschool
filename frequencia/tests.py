from datetime import date, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alunos.models import Aluno
from calendario.models import Categoria, Evento
from matriculas.models import AnoLetivo, Matricula, Turma

from . import servicos
from .models import Chamada, Presenca

S = Presenca.Status


def util_atras(n):
    """n-ésimo dia útil anterior a hoje."""
    d, achados = date.today(), 0
    while achados < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            achados += 1
    return d


class Base(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user("sec", password="x", is_staff=True)
        self.pai = U.objects.create_user("pai", password="x")
        self.client.force_login(self.staff)
        hoje = date.today()
        self.ano = AnoLetivo.objects.create(ano=hoje.year, atual=True)
        self.turma = Turma.objects.create(nome="Jardim II", ano_letivo=self.ano, turno="manha", etapa="infantil_pre")
        self.outra = Turma.objects.create(nome="1º Ano", ano_letivo=self.ano, turno="tarde", etapa="fundamental_iniciais")
        self.ana = self.aluno("Ana Souza", self.turma)
        self.beto = self.aluno("Beto Lima", self.turma)
        self.caio = self.aluno("Caio Reis", self.turma)
        self.dia = util_atras(1)

    def aluno(self, nome, turma, situacao="ativo", matriculado=None):
        a = Aluno.objects.create(nome=nome, data_nascimento=date(2020, 1, 1))
        return Matricula.objects.create(aluno=a, ano_letivo=turma.ano_letivo, turma=turma, mensalidade=D("500"),
                                        data_matricula=matriculado or date(turma.ano_letivo.ano, 1, 1), situacao=situacao)

    def url(self, dia=None, turma=None):
        return reverse("frequencia_chamada", args=[(turma or self.turma).pk, (dia or self.dia).isoformat()])

    def post(self, marcas, dia=None, **extra):
        dados = {}
        for m, (st, *j) in marcas.items():
            dados[f"status_{m.pk}"] = st
            dados[f"just_{m.pk}"] = j[0] if j else ""
        dados.update(extra)
        return self.client.post(self.url(dia), dados)


class ChamadaTests(Base):
    def test_lista_so_alunos_ativos_da_turma(self):
        self.aluno("Dani Transferida", self.turma, situacao="transferido")
        self.aluno("Edu Outra Turma", self.outra)
        r = self.client.get(self.url())
        self.assertContains(r, "Ana Souza")
        self.assertContains(r, "Caio Reis")
        self.assertNotContains(r, "Dani Transferida")
        self.assertNotContains(r, "Edu Outra Turma")

    def test_aluno_matriculado_depois_nao_entra_em_dia_anterior(self):
        self.aluno("Fabi Tardia", self.turma, matriculado=self.dia + timedelta(days=1))
        self.assertNotContains(self.client.get(self.url()), "Fabi Tardia")

    def test_salvar_presenca_falta_e_justificada(self):
        r = self.post({self.ana: (S.PRESENTE,), self.beto: (S.FALTA,), self.caio: (S.JUSTIFICADA, "Atestado médico")},
                      observacao="Passeio")
        self.assertEqual(r.status_code, 302)
        ch = Chamada.objects.get(turma=self.turma, data=self.dia)
        self.assertEqual(ch.observacao, "Passeio")
        self.assertEqual(ch.registrada_por, self.staff)
        self.assertEqual(ch.presencas.get(matricula=self.caio).justificativa, "Atestado médico")
        self.assertEqual(ch.presencas.get(matricula=self.beto).status, "F")
        self.assertEqual(servicos.totais_chamada(ch)["faltas"], 2)

    def test_justificada_exige_justificativa(self):
        r = self.post({self.ana: (S.PRESENTE,), self.beto: (S.JUSTIFICADA, "  "), self.caio: (S.PRESENTE,)})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Informe a justificativa da falta.")
        self.assertFalse(Chamada.objects.exists())

    def test_todos_precisam_de_marcacao(self):
        r = self.post({self.ana: (S.PRESENTE,), self.beto: (S.PRESENTE,)})
        self.assertContains(r, "Marque presença ou falta.")
        self.assertFalse(Chamada.objects.exists())

    def test_resalvar_atualiza_sem_duplicar_e_limpa_justificativa_de_presente(self):
        self.post({self.ana: (S.FALTA, "gripe"), self.beto: (S.PRESENTE,), self.caio: (S.PRESENTE,)})
        self.post({self.ana: (S.PRESENTE, "gripe"), self.beto: (S.PRESENTE,), self.caio: (S.PRESENTE,)})
        self.assertEqual(Chamada.objects.count(), 1)
        self.assertEqual(Presenca.objects.count(), 3)
        self.assertEqual(Presenca.objects.get(matricula=self.ana).justificativa, "")

    def test_editar_mostra_valores_salvos(self):
        self.post({self.ana: (S.JUSTIFICADA, "Viagem"), self.beto: (S.PRESENTE,), self.caio: (S.PRESENTE,)})
        r = self.client.get(self.url())
        self.assertContains(r, 'value="Viagem"')
        self.assertContains(r, "Chamada já registrada")

    def test_aluno_transferido_depois_continua_na_chamada_antiga(self):
        self.post({self.ana: (S.PRESENTE,), self.beto: (S.FALTA,), self.caio: (S.PRESENTE,)})
        self.caio.situacao = "transferido"
        self.caio.save()
        self.assertContains(self.client.get(self.url()), "Caio Reis")
        self.assertNotContains(self.client.get(self.url(util_atras(2))), "Caio Reis")

    def test_dia_futuro_bloqueado(self):
        r = self.client.get(self.url(date.today() + timedelta(days=2)))
        self.assertRedirects(r, reverse("frequencia"), fetch_redirect_response=False)

    def test_data_invalida_404(self):
        self.assertEqual(self.client.get(reverse("frequencia_chamada", args=[self.turma.pk, "xx"])).status_code, 404)

    def test_excluir_chamada(self):
        self.post({self.ana: (S.PRESENTE,), self.beto: (S.PRESENTE,), self.caio: (S.PRESENTE,)})
        self.client.post(reverse("frequencia_chamada_excluir", args=[self.turma.pk, self.dia.isoformat()]))
        self.assertFalse(Chamada.objects.exists())
        self.assertFalse(Presenca.objects.exists())

    def test_excluir_exige_post(self):
        r = self.client.get(reverse("frequencia_chamada_excluir", args=[self.turma.pk, self.dia.isoformat()]))
        self.assertEqual(r.status_code, 405)

    def test_aviso_de_dia_sem_aula_pelo_calendario(self):
        Evento.objects.create(titulo="Feriado teste", categoria=Categoria.FERIADO_ESCOLAR, data_inicio=self.dia, sem_aula=True)
        r = self.client.get(self.url())
        self.assertContains(r, "Feriado teste")
        self.assertFalse(servicos.situacao_do_dia(self.turma, self.dia)[0])
        sabado = self.dia - timedelta(days=(self.dia.weekday() - 5) % 7 or 7)
        self.assertEqual(servicos.situacao_do_dia(self.turma, sabado), (False, "Fim de semana"))

    def test_sabado_letivo_e_dia_letivo(self):
        sabado = date.today() - timedelta(days=(date.today().weekday() - 5) % 7 or 7)
        Evento.objects.create(titulo="Reposição", categoria=Categoria.SABADO_LETIVO, data_inicio=sabado)
        self.assertTrue(servicos.situacao_do_dia(self.turma, sabado)[0])

    def test_evento_so_de_outra_turma_nao_bloqueia(self):
        ev = Evento.objects.create(titulo="Passeio 1º ano", categoria=Categoria.EVENTO, data_inicio=self.dia, sem_aula=True)
        ev.turmas.add(self.outra)
        self.assertTrue(servicos.situacao_do_dia(self.turma, self.dia)[0])
        self.assertFalse(servicos.situacao_do_dia(self.outra, self.dia)[0])


class InicioTests(Base):
    def test_cartoes_mostram_pendente_e_feita(self):
        self.post({self.ana: (S.PRESENTE,), self.beto: (S.FALTA,), self.caio: (S.PRESENTE,)})
        r = self.client.get(reverse("frequencia"), {"data": self.dia.isoformat()})
        self.assertContains(r, "Chamada feita")
        self.assertContains(r, "2 presentes · 1 falta")
        self.assertContains(r, "Chamada pendente")  # a outra turma

    def test_data_futura_vira_hoje(self):
        r = self.client.get(reverse("frequencia"), {"data": (date.today() + timedelta(days=9)).isoformat()})
        self.assertContains(r, 'value="%s"' % date.today().isoformat())


class AcessoTests(Base):
    def test_so_equipe(self):
        urls = [reverse("frequencia"), self.url(), reverse("frequencia_relatorio"),
                reverse("frequencia_consulta_aluno"), reverse("frequencia_aluno", args=[self.ana.aluno.pk])]
        self.client.logout()
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 302, u)
        self.client.force_login(self.pai)
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 403, u)
        self.assertEqual(self.client.post(self.url(), {}).status_code, 403)


class ConsultaERelatorioTests(Base):
    def registrar(self, dias_uteis, marcas_por_dia):
        for n, marcas in zip(dias_uteis, marcas_por_dia):
            self.post(marcas, dia=util_atras(n))

    def cenario(self):
        P, F, J = (S.PRESENTE,), (S.FALTA,), (S.JUSTIFICADA, "Atestado")
        self.registrar([4, 3, 2, 1], [
            {self.ana: P, self.beto: F, self.caio: P},
            {self.ana: P, self.beto: J, self.caio: P},
            {self.ana: P, self.beto: P, self.caio: F},
            {self.ana: P, self.beto: P, self.caio: P},
        ])

    def test_resumo_por_aluno_conta_justificada_como_falta(self):
        self.cenario()
        ini, fim = util_atras(4), date.today()
        r = servicos.resumo_matricula(self.beto, ini, fim)
        self.assertEqual((r["dias"], r["presencas"], r["faltas"], r["justificadas"]), (4, 2, 2, 1))
        self.assertEqual(r["percentual"], D("50.0"))
        self.assertEqual(servicos.resumo_matricula(self.ana, ini, fim)["percentual"], D("100.0"))

    def test_periodo_filtra(self):
        self.cenario()
        r = servicos.resumo_matricula(self.beto, util_atras(2), date.today())
        self.assertEqual(r["dias"], 2)

    def test_pagina_do_aluno(self):
        self.cenario()
        r = self.client.get(reverse("frequencia_aluno", args=[self.beto.aluno.pk]),
                            {"inicio": util_atras(4).isoformat(), "fim": date.today().isoformat()})
        self.assertContains(r, "Atestado")
        self.assertContains(r, "50,0%")
        self.assertContains(r, "Abaixo do mínimo de 60%")  # pré-escola
        self.assertContains(r, "documentos/emitir/declaracao-frequencia/%d/" % self.beto.aluno.pk)
        self.assertContains(r, "da_frequencia=1")

    def test_pagina_do_aluno_sem_chamadas(self):
        r = self.client.get(reverse("frequencia_aluno", args=[self.ana.aluno.pk]))
        self.assertContains(r, "Não há chamadas registradas")

    def test_periodo_invertido_nao_quebra(self):
        r = self.client.get(reverse("frequencia_aluno", args=[self.ana.aluno.pk]),
                            {"inicio": "2026-05-10", "fim": "2026-05-01"})
        self.assertContains(r, "não pode ser depois do fim")

    def test_busca_de_aluno_redireciona(self):
        r = self.client.get(reverse("frequencia_consulta_aluno"), {"aluno": self.ana.aluno.pk})
        self.assertRedirects(r, reverse("frequencia_aluno", args=[self.ana.aluno.pk]), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("frequencia_consulta_aluno"), {"aluno": ""}), "Escolha um aluno")

    def test_relatorio_da_turma(self):
        self.cenario()
        d = servicos.relatorio_turma(self.turma, util_atras(4), date.today())
        self.assertEqual(d["dias_com_chamada"], 4)
        por_nome = {l["aluno"].nome: l for l in d["linhas"]}
        self.assertEqual(por_nome["Beto Lima"]["faltas"], 2)
        self.assertTrue(por_nome["Beto Lima"]["abaixo"])
        self.assertFalse(por_nome["Ana Souza"]["abaixo"])
        self.assertEqual(d["total_faltas"], 3)
        self.assertEqual(d["percentual_turma"], D("75.0"))  # 9 presenças em 12 registros
        self.assertEqual([p.status if p else None for p in por_nome["Beto Lima"]["grade"]], ["F", "J", "P", "P"])

    def test_relatorio_pagina_e_csv(self):
        self.cenario()
        q = {"turma": self.turma.pk, "inicio": util_atras(4).isoformat(), "fim": date.today().isoformat()}
        r = self.client.get(reverse("frequencia_relatorio"), q)
        self.assertContains(r, "Beto Lima")
        self.assertContains(r, "tabela-rolagem")
        csv = self.client.get(reverse("frequencia_relatorio"), {**q, "formato": "csv"})
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        texto = csv.content.decode("utf-8-sig")
        self.assertIn("Beto Lima;4;2;2;1;50,0", texto)

    def test_relatorio_mensal_padrao_e_sem_chamadas(self):
        r = self.client.get(reverse("frequencia_relatorio"), {"turma": self.turma.pk, "mes": "2020-03"})
        self.assertContains(r, "Nenhuma chamada registrada")

    def test_aluno_que_saiu_continua_no_relatorio_do_periodo(self):
        self.cenario()
        self.caio.situacao = "transferido"
        self.caio.save()
        d = servicos.relatorio_turma(self.turma, util_atras(4), date.today())
        self.assertIn("Caio Reis", [l["aluno"].nome for l in d["linhas"]])

    def test_pendentes_apontam_dias_letivos_sem_chamada(self):
        self.registrar([3, 1], [{self.ana: (S.PRESENTE,), self.beto: (S.PRESENTE,), self.caio: (S.PRESENTE,)}] * 2)
        pend = servicos.chamadas_pendentes(self.turma, util_atras(3), date.today())
        self.assertIn(util_atras(2), pend)
        self.assertNotIn(util_atras(3), pend)
        self.assertNotIn(util_atras(1), pend)


class IntegracaoDocumentosTests(Base):
    def test_declaracao_preenche_dias_e_faltas_da_frequencia(self):
        P, F = (S.PRESENTE,), (S.FALTA,)
        self.post({self.ana: P, self.beto: F, self.caio: P}, dia=util_atras(2))
        self.post({self.ana: P, self.beto: F, self.caio: P}, dia=util_atras(1))
        mat = self.beto
        url = reverse("documento_form", args=["declaracao-frequencia", mat.aluno.pk])
        r = self.client.get(url, {"da_frequencia": 1, "matricula": mat.pk,
                                  "periodo_inicio": util_atras(3).isoformat(), "periodo_fim": date.today().isoformat()})
        self.assertContains(r, "preenchidos a partir da frequência diária")
        form = r.context["form"]
        self.assertEqual(form.initial["dias_letivos"], 2)
        self.assertEqual(form.initial["faltas"], 2)

    def test_declaracao_sem_chamadas_avisa(self):
        url = reverse("documento_form", args=["declaracao-frequencia", self.beto.aluno.pk])
        r = self.client.get(url, {"da_frequencia": 1, "matricula": self.beto.pk,
                                  "periodo_inicio": "2020-01-01", "periodo_fim": "2020-02-01"})
        self.assertContains(r, "Não há chamadas registradas nesse período")

    def test_registro_escolar_preenche_pela_frequencia(self):
        self.post({self.ana: (S.PRESENTE,), self.beto: (S.FALTA,), self.caio: (S.PRESENTE,)}, dia=util_atras(1))
        r = self.client.get(reverse("registro_escolar", args=[self.beto.pk]), {"da_frequencia": 1})
        self.assertContains(r, "Preenchido pela frequência diária")
        self.assertEqual(r.context["form"]["dias_letivos"].value(), 1)
        self.assertEqual(r.context["form"]["faltas"].value(), 1)
        # só preenche a tela: nada é gravado até o usuário salvar
        from documentos.models import RegistroEscolar
        self.assertFalse(RegistroEscolar.objects.exists())

    def test_matricula_detail_tem_link(self):
        r = self.client.get(reverse("matricula_detail", args=[self.ana.pk]))
        self.assertContains(r, reverse("frequencia_aluno", args=[self.ana.aluno.pk]))
