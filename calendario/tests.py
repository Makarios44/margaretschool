from datetime import date, time, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from alunos.models import Aluno
from documentos import servicos as doc_servicos
from matriculas.models import AnoLetivo, Matricula, Turma

from . import feriados, servicos
from .ics import _dobrar, gerar_ics
from .models import Categoria, Evento, PeriodoLetivo

C = Categoria


class FeriadosTests(TestCase):
    def test_pascoa_e_datas_moveis(self):
        self.assertEqual(feriados.pascoa(2026), date(2026, 4, 5))
        self.assertEqual(feriados.pascoa(2027), date(2027, 3, 28))
        self.assertEqual(feriados.pascoa(2025), date(2025, 4, 20))
        por_nome = {i["titulo"]: i["data"] for i in feriados.nacionais(2026) + feriados.pontos_facultativos(2026)}
        self.assertEqual(por_nome["Sexta-feira Santa (Paixão de Cristo)"], date(2026, 4, 3))
        self.assertEqual(por_nome["Carnaval (segunda-feira)"], date(2026, 2, 16))
        self.assertEqual(por_nome["Carnaval (terça-feira)"], date(2026, 2, 17))
        self.assertEqual(por_nome["Quarta-feira de Cinzas"], date(2026, 2, 18))
        self.assertEqual(por_nome["Corpus Christi"], date(2026, 6, 4))
        p27 = {i["titulo"]: i["data"] for i in feriados.nacionais(2027) + feriados.pontos_facultativos(2027)}
        self.assertEqual(p27["Sexta-feira Santa (Paixão de Cristo)"], date(2027, 3, 26))
        self.assertEqual(p27["Corpus Christi"], date(2027, 5, 27))

    def test_nacionais_consciencia_negra_so_desde_2024(self):
        self.assertEqual(len(feriados.nacionais(2026)), 10)
        self.assertEqual(len(feriados.nacionais(2023)), 9)
        self.assertIn(date(2026, 11, 20), [i["data"] for i in feriados.nacionais(2026)])

    def test_rn_e_natal(self):
        datas = {(i["categoria"], i["data"]): i["titulo"] for i in feriados.gerar(2026, "RN", "Natal", False)}
        self.assertIn((C.FERIADO_ESTADUAL, date(2026, 10, 3)), datas)
        self.assertIn((C.FERIADO_MUNICIPAL, date(2026, 1, 6)), datas)
        self.assertIn((C.FERIADO_MUNICIPAL, date(2026, 11, 21)), datas)
        # fora de Natal não há municipais pré-cadastrados
        outras = feriados.gerar(2026, "RN", "Mossoró", False)
        self.assertFalse([i for i in outras if i["categoria"] == C.FERIADO_MUNICIPAL])
        self.assertTrue(feriados.tem_municipais("rn", "NATAL"))
        self.assertFalse(feriados.tem_municipais("RN", "Mossoró"))

    def test_comemorativas(self):
        c = {i["titulo"]: i for i in feriados.comemorativas(2026)}
        self.assertEqual(c["Dia das Mães"]["data"], date(2026, 5, 10))
        self.assertEqual(c["Dia dos Pais"]["data"], date(2026, 8, 9))
        self.assertEqual(c["Páscoa"]["data"], date(2026, 4, 5))
        prof = c["Dia do Professor"]
        self.assertEqual((prof["categoria"], prof["sem_aula"]), (C.FERIADO_ESCOLAR, True))


class GeracaoTests(TestCase):
    def test_gerar_e_idempotencia(self):
        criados, existentes = servicos.gerar_feriados(2026, "RN", "Natal")
        self.assertGreater(criados, 20)
        self.assertEqual(existentes, 0)
        n = Evento.objects.count()
        criados2, existentes2 = servicos.gerar_feriados(2026, "RN", "Natal")
        self.assertEqual((criados2, existentes2), (0, n))
        self.assertEqual(Evento.objects.count(), n)
        carnaval = Evento.objects.get(titulo="Carnaval (terça-feira)")
        self.assertTrue(carnaval.sem_aula)
        self.assertEqual(carnaval.categoria, C.PONTO_FACULTATIVO)
        self.assertFalse(Evento.objects.get(titulo="Quarta-feira de Cinzas").sem_aula)

    def test_repete_anualmente(self):
        aniversario = Evento.objects.create(
            titulo="Aniversário da escola", categoria=C.EVENTO, data_inicio=date(2026, 3, 15),
            data_fim=date(2026, 3, 16), repete_anualmente=True)
        servicos.gerar_feriados(2027, "RN", "Natal", False)
        copia = Evento.objects.get(titulo="Aniversário da escola", data_inicio__year=2027)
        self.assertEqual((copia.data_inicio, copia.data_fim), (date(2027, 3, 15), date(2027, 3, 16)))
        servicos.gerar_feriados(2027, "RN", "Natal", False)  # sem duplicar
        self.assertEqual(Evento.objects.filter(titulo="Aniversário da escola").count(), 2)
        self.assertTrue(Evento.objects.get(pk=aniversario.pk).repete_anualmente)


class DiasLetivosTests(TestCase):
    def setUp(self):
        self.ano = AnoLetivo.objects.create(
            ano=2026, inicio_aulas=date(2026, 3, 2), fim_aulas=date(2026, 3, 13), horas_dia_letivo=D("4"))

    def test_conta_dias_uteis_feriados_e_sabado_letivo(self):
        r = servicos.dias_letivos(self.ano)
        self.assertEqual(r["total"], 10)  # 2 semanas úteis
        Evento.objects.create(titulo="Feriado local", categoria=C.FERIADO_MUNICIPAL,
                              data_inicio=date(2026, 3, 4), sem_aula=True)
        Evento.objects.create(titulo="Reposição", categoria=C.SABADO_LETIVO, data_inicio=date(2026, 3, 7))
        r = servicos.dias_letivos(self.ano)
        self.assertEqual(r["total"], 10)  # -1 feriado, +1 sábado letivo
        self.assertEqual(r["dias_sem_aula"], [date(2026, 3, 4)])
        self.assertEqual(r["sabados_letivos"], [date(2026, 3, 7)])
        self.assertEqual(r["horas"], D("40"))
        self.assertEqual(r["faltam_dias"], 190)
        self.assertFalse(r["atende_dias"])
        self.assertFalse(r["atende_horas"])

    def test_feriado_no_fim_de_semana_nao_conta_e_recesso_longo(self):
        Evento.objects.create(titulo="Feriado no sábado", categoria=C.FERIADO_NACIONAL,
                              data_inicio=date(2026, 3, 7), sem_aula=True)
        Evento.objects.create(titulo="Recesso", categoria=C.RECESSO, data_inicio=date(2026, 3, 9),
                              data_fim=date(2026, 3, 11), sem_aula=True)
        r = servicos.dias_letivos(self.ano)
        self.assertEqual(r["total"], 7)
        self.assertEqual(len(r["dias_sem_aula"]), 3)

    def test_evento_de_uma_turma_nao_entra_na_conta_geral(self):
        t = Turma.objects.create(nome="Jardim", ano_letivo=self.ano, turno="manha")
        ev = Evento.objects.create(titulo="Passeio", categoria=C.EVENTO, data_inicio=date(2026, 3, 4), sem_aula=True)
        ev.turmas.add(t)
        self.assertEqual(servicos.dias_letivos(self.ano)["total"], 10)

    def test_minimo_atingido_e_periodos(self):
        ano = AnoLetivo.objects.create(ano=2027, inicio_aulas=date(2027, 2, 1), fim_aulas=date(2027, 12, 17),
                                       horas_dia_letivo=D("4"))
        PeriodoLetivo.objects.create(ano_letivo=ano, nome="1º semestre", inicio=date(2027, 2, 1), fim=date(2027, 6, 30))
        r = servicos.dias_letivos(ano)
        self.assertGreater(r["total"], 200)  # sem feriados cadastrados, passa fácil
        self.assertTrue(r["atende_dias"] and r["atende_horas"])
        self.assertEqual(len(r["periodos"]), 1)
        self.assertGreater(r["periodos"][0]["dias"], 80)

    def test_sem_configuracao(self):
        ano = AnoLetivo.objects.create(ano=2030)
        self.assertIsNone(servicos.dias_letivos(ano))
        self.assertEqual(servicos.contagem_mensal(ano), {})


class IcsTests(TestCase):
    def test_formato(self):
        dia = Evento.objects.create(titulo="Festa, junina; da escola", categoria=C.EVENTO,
                                    data_inicio=date(2026, 6, 20), data_fim=date(2026, 6, 21),
                                    descricao="Linha 1\nLinha 2", sem_aula=True)
        hora = Evento.objects.create(titulo="Reunião", categoria=C.REUNIAO_PAIS, data_inicio=date(2026, 5, 4),
                                     hora_inicio=time(19, 0), hora_fim=time(20, 30), local="Auditório")
        txt = gerar_ics([dia, hora], "Calendário — Teste")
        self.assertTrue(txt.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(txt.endswith("END:VCALENDAR\r\n"))
        self.assertIn("DTSTART;VALUE=DATE:20260620", txt)
        self.assertIn("DTEND;VALUE=DATE:20260622", txt)  # fim exclusivo
        self.assertIn("SUMMARY:Festa\\, junina\\; da escola", txt)
        self.assertIn("DESCRIPTION:Não há aula. Linha 1\\nLinha 2", txt)
        self.assertIn("DTSTART:20260504T190000", txt)
        self.assertIn("DTEND:20260504T203000", txt)
        self.assertIn("LOCATION:Auditório", txt)

    def test_dobra_de_linhas(self):
        for linha in _dobrar("DESCRIPTION:" + "ação " * 60):
            self.assertLessEqual(len(linha.encode("utf-8")), 75)


class VisoesTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("sec", password="x", is_staff=True)
        self.pai = get_user_model().objects.create_user("pai", password="x")
        self.publico = Evento.objects.create(titulo="Reunião de pais", categoria=C.REUNIAO_PAIS,
                                             data_inicio=date(2026, 10, 20), hora_inicio=time(19, 0))
        self.interno = Evento.objects.create(titulo="Planejamento secreto", categoria=C.PLANEJAMENTO,
                                             data_inicio=date(2026, 10, 21), publico=False)
        self.feriado = Evento.objects.create(titulo="Feriado teste", categoria=C.FERIADO_NACIONAL,
                                             data_inicio=date(2026, 10, 12), sem_aula=True)

    def test_publico_ve_so_eventos_publicos(self):
        r = self.client.get(reverse("calendario_mes", args=[2026, 10]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'title="Reunião de pais"')  # o chip do evento na grade
        self.assertContains(r, "19:00")
        self.assertNotContains(r, "Planejamento secreto")
        self.assertContains(r, "Outubro de 2026")  # sem separador de milhar
        self.assertEqual(self.client.get(reverse("evento_detail", args=[self.interno.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("evento_detail", args=[self.publico.pk])).status_code, 200)

    def test_equipe_ve_internos_e_aniversarios_publico_nunca(self):
        ano = AnoLetivo.objects.create(ano=2026)
        t = Turma.objects.create(nome="Jardim", ano_letivo=ano, turno="manha")
        aluno = Aluno.objects.create(nome="Maria Clara Souza", data_nascimento=date(2021, 10, 22))
        Matricula.objects.create(aluno=aluno, ano_letivo=ano, turma=t, mensalidade=D("500"))
        url = reverse("calendario_mes", args=[2026, 10]) + "?aniv=1"
        anon = self.client.get(url)
        self.assertNotContains(anon, "Maria")  # privacidade de crianças
        self.client.force_login(self.staff)
        r = self.client.get(url)
        self.assertContains(r, "Planejamento secreto")
        self.assertContains(r, "Aniversário: Maria (5 anos)")
        sem = self.client.get(reverse("calendario_mes", args=[2026, 10]))
        self.assertNotContains(sem, "Aniversário: Maria")

    def test_grade_do_mes_e_filtros(self):
        r = self.client.get(reverse("calendario_mes", args=[2026, 10]))
        semanas = r.context["semanas"]
        self.assertEqual(semanas[0][0]["data"].weekday(), 6)  # semana começa no domingo
        dias = {d["data"]: d for s in semanas for d in s}
        self.assertTrue(dias[date(2026, 10, 12)]["sem_aula"])
        self.assertEqual(len(dias[date(2026, 10, 20)]["eventos"]), 1)
        r = self.client.get(reverse("calendario_mes", args=[2026, 10]) + "?cat=avaliacao")
        self.assertFalse(any(d["eventos"] for sem in r.context["semanas"] for d in sem))
        self.assertNotContains(r, 'title="Reunião de pais"')
        r = self.client.get(reverse("calendario_mes", args=[2026, 10]) + "?cat=reuniao_pais")
        self.assertContains(r, 'title="Reunião de pais"')
        self.assertNotContains(r, 'title="Feriado teste"')
        self.assertEqual(self.client.get(reverse("calendario_mes", args=[2026, 13])).status_code, 404)
        self.assertEqual(self.client.get(reverse("calendario_mes", args=[1500, 1])).status_code, 404)

    def test_ano_e_agenda_e_impressao(self):
        r = self.client.get(reverse("calendario_ano", args=[2026]))
        self.assertContains(r, "Outubro")
        self.assertContains(r, "Feriado teste")
        self.assertNotContains(r, "Planejamento secreto")
        imp = self.client.get(reverse("calendario_imprimir", args=[2026]))
        self.assertContains(imp, "Calendário escolar 2026")
        self.assertNotContains(imp, "Planejamento secreto")
        self.assertNotContains(imp, "Baixar PDF")  # PDF direto é só da equipe
        hoje = date.today()
        Evento.objects.create(titulo="Evento futuro", categoria=C.EVENTO, data_inicio=hoje + timedelta(days=10))
        self.assertContains(self.client.get(reverse("calendario_agenda")), "Evento futuro")
        self.assertContains(self.client.get(reverse("calendario_ano", args=[2026])), "Calendário 2026")

    def test_ics_publico(self):
        r = self.client.get(reverse("calendario_ics"))
        self.assertEqual(r["Content-Type"], "text/calendar; charset=utf-8")
        corpo = r.content.decode()
        self.assertIn("Reunião de pais", corpo)
        self.assertNotIn("Planejamento secreto", corpo)

    def test_pdf_do_calendario(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("calendario_pdf", args=[2026]))
        if doc_servicos.pdf_disponivel():
            self.assertTrue(r.content.startswith(b"%PDF"))
        else:
            self.assertEqual(r.status_code, 302)
        self.client.force_login(self.pai)
        self.assertEqual(self.client.get(reverse("calendario_pdf", args=[2026])).status_code, 403)

    def test_painel_mostra_proximos_eventos(self):
        Evento.objects.create(titulo="Prova bimestral", categoria=C.AVALIACAO,
                              data_inicio=date.today() + timedelta(days=3))
        self.client.force_login(self.pai)
        self.assertContains(self.client.get(reverse("dashboard")), "Prova bimestral")


class GestaoTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("sec", password="x", is_staff=True)
        self.client.force_login(self.staff)

    def dados(self, **kw):
        d = {"titulo": "Festa junina", "categoria": "evento", "data_inicio": "2026-06-20", "publico": "on"}
        d.update(kw)
        return d

    def test_criar_editar_excluir_evento(self):
        r = self.client.post(reverse("evento_create"), self.dados(hora_inicio="18:00", hora_fim="21:00"))
        self.assertEqual(r.status_code, 302)
        ev = Evento.objects.get()
        self.assertEqual(ev.origem, "manual")
        self.client.post(reverse("evento_update", args=[ev.pk]), self.dados(titulo="Festa junina 2026", sem_aula="on"))
        ev.refresh_from_db()
        self.assertEqual((ev.titulo, ev.sem_aula), ("Festa junina 2026", True))
        self.assertEqual(self.client.get(reverse("evento_delete", args=[ev.pk])).status_code, 405)
        self.client.post(reverse("evento_delete", args=[ev.pk]))
        self.assertFalse(Evento.objects.exists())

    def test_validacoes(self):
        r = self.client.post(reverse("evento_create"), self.dados(data_fim="2026-06-10"))
        self.assertContains(r, "igual ou depois")
        r = self.client.post(reverse("evento_create"), self.dados(hora_inicio="20:00", hora_fim="19:00"))
        self.assertContains(r, "depois do início")
        self.assertFalse(Evento.objects.exists())

    @override_settings(CALENDARIO={"uf": "RN", "municipio": "Natal"})
    def test_gerar_feriados_pela_tela(self):
        r = self.client.get(reverse("feriados_gerar") + "?ano=2026")
        self.assertContains(r, "Dia de Reis")
        self.assertContains(r, "Mártires de Cunhaú e Uruaçu")
        self.client.post(reverse("feriados_gerar"), {"ano": 2026, "comemorativas": "on"})
        self.assertTrue(Evento.objects.filter(titulo="Dia de Reis", data_inicio="2026-01-06").exists())
        self.assertTrue(Evento.objects.filter(titulo="Dia das Mães").exists())
        self.client.post(reverse("feriados_gerar"), {"ano": 2027})  # sem comemorativas
        self.assertFalse(Evento.objects.filter(titulo="Dia das Mães", data_inicio__year=2027).exists())

    @override_settings(CALENDARIO={"uf": "RN", "municipio": "Mossoró"})
    def test_municipio_sem_feriados_cadastrados_avisa(self):
        r = self.client.get(reverse("feriados_gerar") + "?ano=2026")
        self.assertContains(r, "Ainda não há feriados municipais")

    def test_configurar_ano_e_relatorio(self):
        ano = AnoLetivo.objects.create(ano=2026, atual=True)
        url = reverse("ano_configurar", args=[ano.pk])
        base = {"inicio_aulas": "2026-02-02", "fim_aulas": "2026-12-18", "horas_dia_letivo": "4.0",
                "per-TOTAL_FORMS": 1, "per-INITIAL_FORMS": 0, "per-MIN_NUM_FORMS": 0, "per-MAX_NUM_FORMS": 1000,
                "per-0-nome": "1º bimestre", "per-0-inicio": "2026-02-02", "per-0-fim": "2026-04-17"}
        r = self.client.post(url, {**base, "fim_aulas": "2026-01-01"})
        self.assertContains(r, "depois do início")
        r = self.client.post(url, {**base, "fim_aulas": ""})
        self.assertContains(r, "Informe o início e o fim")
        self.assertEqual(self.client.post(url, base).status_code, 302)
        r = self.client.get(reverse("dias_letivos") + f"?ano={ano.pk}")
        self.assertContains(r, "1º bimestre")
        self.assertGreater(r.context["r"]["total"], 200)
        self.assertContains(r, "Mínimo atingido")

    def test_somente_equipe(self):
        self.client.force_login(get_user_model().objects.create_user("pai", password="x"))
        for nome, args in [("evento_list", []), ("evento_create", []), ("feriados_gerar", []), ("dias_letivos", [])]:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 403, nome)
        self.assertEqual(self.client.post(reverse("feriados_gerar"), {"ano": 2026}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("evento_list")).status_code, 302)
