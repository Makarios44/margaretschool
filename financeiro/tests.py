from datetime import date, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from alunos.models import Aluno, ContatoEmergencia, Responsavel
from matriculas.models import AnoLetivo, Matricula, Turma

from .extenso import valor_por_extenso
from .models import Cobranca

CFG = {"multa_percentual": D("2"), "juros_mensal_percentual": D("1")}
HOJE = date.today()


class ExtensoTests(TestCase):
    def test_valores(self):
        casos = {
            "1": "um real",
            "0.50": "cinquenta centavos",
            "0.01": "um centavo",
            "21": "vinte e um reais",
            "100": "cem reais",
            "101": "cento e um reais",
            "120.35": "cento e vinte reais e trinta e cinco centavos",
            "1000": "mil reais",
            "1001": "mil e um reais",
            "1230": "mil duzentos e trinta reais",
            "1234.56": "mil duzentos e trinta e quatro reais e cinquenta e seis centavos",
            "2500": "dois mil e quinhentos reais",
            "600": "seiscentos reais",
            "1000000": "um milhão de reais",
            "1000100": "um milhão e cem reais",
            "2500000": "dois milhões e quinhentos mil reais",
            "0": "zero real",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(valor_por_extenso(D(entrada)), esperado, entrada)


class Base(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("sec", password="x", is_staff=True)
        self.client.force_login(self.staff)
        self.ano = AnoLetivo.objects.create(ano=HOJE.year, atual=True)
        self.turma = Turma.objects.create(nome="Maternal II", ano_letivo=self.ano, turno="manha")
        self.aluno = Aluno.objects.create(nome="Pedro Lima", data_nascimento=date(2022, 5, 1))
        Responsavel.objects.create(aluno=self.aluno, nome="Ana Lima", parentesco="mae",
                                   telefone="84 99999-1111", responsavel_financeiro=True)
        ContatoEmergencia.objects.create(aluno=self.aluno, nome="Rita", parentesco="tia", telefone="2")
        self.mat = Matricula.objects.create(
            aluno=self.aluno, ano_letivo=self.ano, turma=self.turma, data_matricula=date(HOJE.year, 1, 10),
            taxa_matricula=D("150"), mensalidade=D("600"), dia_vencimento=10,
        )

    def cobranca(self, dias_para_vencer=0, **kw):
        dados = dict(matricula=self.mat, descricao="Cobrança teste", tipo="avulsa",
                     vencimento=HOJE + timedelta(days=dias_para_vencer), valor=D("600"))
        dados.update(kw)
        return Cobranca.objects.create(**dados)


@override_settings(FINANCEIRO=CFG)
class ModeloTests(Base):
    def test_encargos_por_atraso(self):
        c = self.cobranca(dias_para_vencer=-10)
        multa, juros = c.calcular_encargos()
        self.assertEqual(multa, D("12.00"))   # 2% de 600
        self.assertEqual(juros, D("2.00"))    # 1% a.m. / 30 * 10 dias
        self.assertEqual(c.valor_atualizado, D("614.00"))
        self.assertEqual(c.status, "vencida")

    def test_sem_encargos_no_prazo_e_desconto_reduz_base(self):
        c = self.cobranca(dias_para_vencer=0)
        self.assertEqual(c.calcular_encargos(), (D("0.00"), D("0.00")))
        self.assertEqual(c.status, "pendente")
        c2 = self.cobranca(dias_para_vencer=-30, desconto=D("100"), descricao="b")
        self.assertEqual(c2.calcular_encargos(), (D("10.00"), D("5.00")))  # base 500

    def test_pagamento_estorno_e_taxa(self):
        taxa = self.cobranca(tipo="taxa_matricula", valor=D("150"), descricao="Taxa")
        taxa.registrar_pagamento(HOJE, "pix")
        self.mat.refresh_from_db()
        self.assertTrue(self.mat.taxa_paga)
        self.assertEqual(taxa.valor_pago, D("150.00"))
        self.assertTrue(taxa.recibo_numero.startswith(str(HOJE.year)))
        taxa.estornar()
        self.mat.refresh_from_db()
        self.assertFalse(self.mat.taxa_paga)
        self.assertIsNone(taxa.valor_pago)
        self.assertTrue(taxa.aberta)

    def test_pagar_duas_vezes_falha(self):
        c = self.cobranca()
        c.registrar_pagamento(HOJE, "dinheiro")
        with self.assertRaises(ValueError):
            c.registrar_pagamento(HOJE, "dinheiro")

    def test_mensalidade_duplicada_bloqueada_e_cancelada_libera(self):
        a = self.cobranca(vencimento=date(HOJE.year, 3, 10), tipo="mensalidade")
        form_dup = Cobranca(matricula=self.mat, tipo="mensalidade", descricao="x",
                            vencimento=date(HOJE.year, 3, 20), valor=D("1"))
        with self.assertRaises(Exception):
            form_dup.full_clean()
        a.cancelar()
        form_dup.full_clean()  # agora pode

    def test_bolsa_na_matricula(self):
        self.mat.desconto_percentual = D("50")
        self.assertEqual(self.mat.desconto_valor, D("300.00"))
        self.assertEqual(self.mat.mensalidade_liquida, D("300.00"))


@override_settings(FINANCEIRO=CFG)
class FluxoTests(Base):
    def test_gerar_mensalidades_com_bolsa_e_taxa(self):
        self.mat.desconto_percentual = D("50")
        self.mat.desconto_motivo = "Irmão na escola"
        self.mat.save()
        url = reverse("gerar_mensalidades", args=[self.mat.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "taxa de matrícula")
        r = self.client.post(url, {"mes_inicial": 1, "quantidade": 12, "incluir_taxa": "on"})
        self.assertEqual(r.status_code, 302)
        mens = self.mat.cobrancas.filter(tipo="mensalidade")
        self.assertEqual(mens.count(), 12)
        jan = mens.get(competencia=date(HOJE.year, 1, 1))
        self.assertEqual((jan.valor, jan.desconto), (D("600"), D("300.00")))
        self.assertEqual(jan.motivo_desconto, "Irmão na escola")
        self.assertEqual(jan.vencimento, date(HOJE.year, 1, 10))
        self.assertEqual(self.mat.cobrancas.filter(tipo="taxa_matricula").count(), 1)
        # gerar de novo não duplica
        self.client.post(url, {"mes_inicial": 1, "quantidade": 12})
        self.assertEqual(self.mat.cobrancas.filter(tipo="mensalidade").count(), 12)

    def test_gerar_nao_passa_de_dezembro(self):
        url = reverse("gerar_mensalidades", args=[self.mat.pk])
        r = self.client.post(url, {"mes_inicial": 10, "quantidade": 6})
        self.assertContains(r, "passar de dezembro")
        self.assertEqual(Cobranca.objects.count(), 0)

    def test_receber_com_atraso_e_recibo(self):
        c = self.cobranca(dias_para_vencer=-10)
        r = self.client.get(reverse("cobranca_receber", args=[c.pk]))
        self.assertEqual(r.context["form"].initial["multa"], D("12.00"))
        r = self.client.post(reverse("cobranca_receber", args=[c.pk]), {
            "data_pagamento": HOJE.isoformat(), "forma_pagamento": "pix",
            "desconto": "0", "multa": "12.00", "juros": "2.00",
        })
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual((c.situacao, c.valor_pago, c.forma_pagamento), ("paga", D("614.00"), "pix"))
        rec = self.client.get(reverse("cobranca_recibo", args=[c.pk]))
        self.assertContains(rec, "seiscentos e quatorze reais")
        self.assertContains(rec, "Ana Lima")
        self.assertContains(rec, "Pix")

    def test_receber_isentando_multa_e_validacoes(self):
        c = self.cobranca(dias_para_vencer=-10)
        url = reverse("cobranca_receber", args=[c.pk])
        base = {"data_pagamento": HOJE.isoformat(), "forma_pagamento": "dinheiro"}
        r = self.client.post(url, {**base, "forma_pagamento": ""})
        self.assertEqual(r.status_code, 200)  # forma obrigatória
        r = self.client.post(url, {**base, "data_pagamento": (HOJE + timedelta(days=2)).isoformat()})
        self.assertContains(r, "não pode ser no futuro")
        r = self.client.post(url, {**base, "desconto": "9999"})
        self.assertContains(r, "não pode ser maior")
        self.client.post(url, {**base, "multa": "", "juros": "", "desconto": "50"})
        c.refresh_from_db()
        self.assertEqual(c.valor_pago, D("550.00"))  # 600 - 50 de abatimento, sem encargos

    def test_cancelar_estornar_e_editar_restrito(self):
        c = self.cobranca()
        self.client.post(reverse("cobranca_cancelar", args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.situacao, "cancelada")
        self.assertEqual(self.client.get(reverse("cobranca_update", args=[c.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("cobranca_recibo", args=[c.pk])).status_code, 302)
        p = self.cobranca(descricao="p")
        p.registrar_pagamento(HOJE, "cartao")
        self.client.post(reverse("cobranca_estornar", args=[p.pk]))
        p.refresh_from_db()
        self.assertTrue(p.aberta)
        # ações destrutivas exigem POST
        self.assertEqual(self.client.get(reverse("cobranca_cancelar", args=[p.pk])).status_code, 405)

    def test_cobranca_avulsa_e_edicao(self):
        r = self.client.post(reverse("cobranca_create"), {
            "matricula": self.mat.pk, "tipo": "avulsa", "descricao": "Uniforme",
            "vencimento": HOJE.isoformat(), "valor": "80.00", "desconto": "",
        })
        self.assertEqual(r.status_code, 302)
        c = Cobranca.objects.get()
        self.assertEqual(c.desconto, 0)
        r = self.client.post(reverse("cobranca_update", args=[c.pk]), {
            "matricula": self.mat.pk, "tipo": "avulsa", "descricao": "Uniforme",
            "vencimento": HOJE.isoformat(), "valor": "80.00", "desconto": "100",
        })
        self.assertContains(r, "não pode ser maior")

    def test_lista_filtros_e_resumo(self):
        self.cobranca(dias_para_vencer=-3, descricao="Vencida")
        self.cobranca(dias_para_vencer=0, descricao="Em dia")
        paga = self.cobranca(dias_para_vencer=0, descricao="Quitada")
        paga.registrar_pagamento(HOJE, "pix")
        r = self.client.get(reverse("cobranca_list") + "?mes=")
        self.assertEqual(r.context["resumo"]["previsto"], D("1800.00"))
        self.assertEqual(r.context["resumo"]["recebido"], D("600.00"))
        self.assertEqual(r.context["resumo"]["vencido"], D("600.00"))
        r = self.client.get(reverse("cobranca_list") + "?mes=&status=vencida")
        self.assertContains(r, "Vencida")
        self.assertNotContains(r, "Em dia")
        r = self.client.get(reverse("cobranca_list") + "?mes=&status=paga")
        self.assertContains(r, "Quitada")

    def test_relatorio_mensal(self):
        mes_ref = HOJE.replace(day=1)
        # recebido em dinheiro e pix neste mês
        a = self.cobranca(dias_para_vencer=0, descricao="A")
        a.registrar_pagamento(HOJE, "pix")
        b = self.cobranca(dias_para_vencer=0, descricao="B", desconto=D("100"))
        b.registrar_pagamento(HOJE, "dinheiro")
        # vencida em aberto com vencimento no mês passado (entra só na acumulada)
        ontem = HOJE - timedelta(days=1)
        v = self.cobranca(descricao="C", vencimento=ontem)
        r = self.client.get(reverse("relatorio_mensal") + f"?mes={mes_ref:%Y-%m}")
        self.assertEqual(r.status_code, 200)
        ctx = r.context
        self.assertEqual(ctx["caixa"]["total"], D("1100.00"))
        formas = {f["nome"]: f["total"] for f in ctx["por_forma"]}
        self.assertEqual(formas, {"Pix": D("600.00"), "Dinheiro": D("500.00")})
        self.assertEqual(ctx["acumulada"]["total"], D("600.00"))
        if ontem.month == HOJE.month:  # "ontem" ainda cai no mesmo mês
            self.assertEqual(ctx["comp"]["vencido"], D("600.00"))
            self.assertEqual(ctx["comp"]["n_alunos"], 1)
            self.assertContains(r, "Ana Lima")
            self.assertEqual(ctx["comp"]["previsto"], D("1700.00"))  # 600 + 500 (com desconto) + 600
            self.assertEqual(ctx["comp"]["inadimplencia_pct"], D("35.3"))  # 600 / 1700
        # mês sem movimento
        r = self.client.get(reverse("relatorio_mensal") + "?mes=2000-01")
        self.assertEqual(r.context["caixa"]["total"], D("0.00"))
        r = self.client.get(reverse("relatorio_mensal") + "?mes=lixo")  # inválido volta ao mês atual
        self.assertEqual(r.status_code, 200)

    def test_matricula_mostra_financeiro_e_contrato_com_encargos(self):
        self.cobranca(descricao="Mensalidade X")
        r = self.client.get(reverse("matricula_detail", args=[self.mat.pk]))
        self.assertContains(r, "Mensalidade X")
        c = self.client.get(reverse("matricula_contrato", args=[self.mat.pk]))
        self.assertContains(c, "multa de 2%")
        self.assertContains(c, "juros de mora de 1%")

    def test_somente_equipe(self):
        c = self.cobranca()
        self.client.force_login(get_user_model().objects.create_user("pai", password="x"))
        for name, args in [("cobranca_list", []), ("relatorio_mensal", []),
                           ("cobranca_receber", [c.pk]), ("cobranca_recibo", [c.pk]),
                           ("gerar_mensalidades", [self.mat.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("cobranca_list")).status_code, 302)


@override_settings(FINANCEIRO=CFG)
class FormatoNumericoTests(Base):
    def test_valores_com_milhar_e_ids_sem_separador(self):
        c = self.cobranca(valor=D("1234.50"), descricao="Anuidade")
        c.registrar_pagamento(HOJE, "pix")
        recibo = self.client.get(reverse("cobranca_recibo", args=[c.pk]))
        self.assertContains(recibo, "1.234,50")  # dinheiro: separador de milhar e vírgula
        self.assertContains(recibo, "mil duzentos e trinta e quatro reais")
        # números que não são dinheiro (códigos, anos) nunca recebem separador
        from django.template import Context, Template
        self.assertEqual(Template("{{ n }}").render(Context({"n": 2026})), "2026")
        self.assertEqual(Template("{{ n }}").render(Context({"n": 12345})), "12345")


# ===================== Despesas e painel financeiro =====================
import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from .models import CategoriaDespesa, Despesa  # noqa: E402

TMP_MEDIA_DESP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA_DESP)
class DespesaTests(Base):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP_MEDIA_DESP, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.cat = CategoriaDespesa.objects.get(nome="Material didático e livros")
        self.cat2 = CategoriaDespesa.objects.get(nome="Aluguel")

    def dados(self, **kw):
        d = {"data": HOJE.isoformat(), "descricao": "30 livros de leitura", "categoria": self.cat.pk,
             "valor": "450.90", "fornecedor": "Livraria Central", "forma_pagamento": "pix"}
        d.update(kw)
        return d

    def lancar(self, descricao="Compra", valor="100", data=None, categoria=None, **kw):
        return Despesa.objects.create(
            data=data or HOJE, descricao=descricao, categoria=categoria or self.cat, valor=D(valor),
            forma_pagamento=kw.pop("forma_pagamento", "pix"), **kw)

    def test_lancar_com_comprovante_e_ver_detalhe(self):
        pdf = SimpleUploadedFile("nota.pdf", b"%PDF-1.4 teste", content_type="application/pdf")
        r = self.client.post(reverse("despesa_create"), self.dados(comprovante=pdf, numero_documento="NF 123"))
        self.assertEqual(r.status_code, 302)
        d = Despesa.objects.get()
        self.assertEqual((d.valor, d.categoria, d.criado_por), (D("450.90"), self.cat, self.staff))
        self.assertTrue(d.comprovante.name.endswith(".pdf"))
        det = self.client.get(reverse("despesa_detail", args=[d.pk]))
        self.assertContains(det, "30 livros de leitura")
        self.assertContains(det, "450,90")
        self.assertContains(det, "NF 123")
        self.assertContains(det, "Abrir comprovante")

    def test_salvar_e_lancar_outra(self):
        r = self.client.post(reverse("despesa_create"), self.dados(acao="salvar_e_novo"))
        self.assertRedirects(r, reverse("despesa_create"))
        self.assertEqual(Despesa.objects.count(), 1)

    def test_validacoes(self):
        url = reverse("despesa_create")
        casos = [
            ({"valor": "0"}, "maior ou igual"),
            ({"valor": "-5"}, "maior ou igual"),
            ({"data": (HOJE + timedelta(days=1)).isoformat()}, "no futuro"),
            ({"categoria": ""}, "obrigatório"),
            ({"forma_pagamento": ""}, "obrigatório"),
        ]
        for kw, texto in casos:
            r = self.client.post(url, self.dados(**kw))
            self.assertContains(r, texto, msg_prefix=str(kw))
        ruim = SimpleUploadedFile("virus.exe", b"x", content_type="application/octet-stream")
        self.assertContains(self.client.post(url, self.dados(comprovante=ruim)), "não é permitida")
        grande = SimpleUploadedFile("grande.pdf", b"0" * (5 * 1024 * 1024 + 1), content_type="application/pdf")
        self.assertContains(self.client.post(url, self.dados(comprovante=grande)), "maior que 5 MB")
        self.assertEqual(Despesa.objects.count(), 0)

    def test_categoria_desativada_some_do_lancamento_mas_continua_na_despesa_antiga(self):
        d = self.lancar(categoria=self.cat2)
        self.cat2.ativa = False
        self.cat2.save()
        novo = self.client.get(reverse("despesa_create"))
        self.assertNotContains(novo, f'value="{self.cat2.pk}"')
        edicao = self.client.get(reverse("despesa_update", args=[d.pk]))
        self.assertContains(edicao, f'value="{self.cat2.pk}"')

    def test_editar_e_excluir(self):
        d = self.lancar("Antes", "10")
        self.client.post(reverse("despesa_update", args=[d.pk]), self.dados(descricao="Depois", valor="20"))
        d.refresh_from_db()
        self.assertEqual((d.descricao, d.valor), ("Depois", D("20.00")))
        self.assertEqual(self.client.get(reverse("despesa_delete", args=[d.pk])).status_code, 405)
        self.client.post(reverse("despesa_delete", args=[d.pk]))
        self.assertFalse(Despesa.objects.exists())

    def test_lista_filtros_e_total(self):
        self.lancar("Livros", "100", categoria=self.cat, fornecedor="Livraria X")
        self.lancar("Aluguel de outubro", "2000", categoria=self.cat2, forma_pagamento="boleto")
        self.lancar("Antiga", "50", data=HOJE.replace(day=1) - timedelta(days=40))
        r = self.client.get(reverse("despesa_list"))  # mês atual por padrão
        self.assertEqual(r.context["total"], D("2100"))
        self.assertEqual(r.context["quantidade"], 2)
        self.assertContains(r, "2.100,00")
        self.assertEqual(self.client.get(reverse("despesa_list") + "?mes=").context["total"], D("2150"))
        self.assertEqual(self.client.get(reverse("despesa_list") + f"?categoria={self.cat2.pk}").context["total"], D("2000"))
        self.assertEqual(self.client.get(reverse("despesa_list") + "?forma=boleto").context["quantidade"], 1)
        self.assertEqual(self.client.get(reverse("despesa_list") + "?q=livraria").context["total"], D("100"))

    def test_exportar_csv(self):
        self.lancar("Café, açúcar e filtro", "1234.5", fornecedor="Mercado")
        r = self.client.get(reverse("despesa_list") + "?formato=csv")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        texto = r.content.decode("utf-8")
        self.assertTrue(texto.startswith("\ufeffData;Descrição;Categoria"))
        self.assertIn(";Café, açúcar e filtro;", texto)  # o separador é ;, então a vírgula não precisa de aspas
        self.assertIn("1234,50", texto)

    def test_somente_equipe(self):
        d = self.lancar()
        self.client.force_login(get_user_model().objects.create_user("pai", password="x"))
        for nome, args in [("financeiro_painel", []), ("despesa_list", []), ("despesa_create", []),
                           ("despesa_detail", [d.pk]), ("despesa_update", [d.pk])]:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 403, nome)
        self.assertEqual(self.client.post(reverse("despesa_delete", args=[d.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("financeiro_painel")).status_code, 302)


@override_settings(FINANCEIRO=CFG)
class PainelFinanceiroTests(Base):
    def setUp(self):
        super().setUp()
        self.cat = CategoriaDespesa.objects.get(nome="Material didático e livros")
        self.cat2 = CategoriaDespesa.objects.get(nome="Aluguel")
        self.ano = HOJE.year

    def despesa(self, mes, valor, categoria=None, descricao="x"):
        Despesa.objects.create(data=date(self.ano, mes, 15), descricao=descricao, categoria=categoria or self.cat,
                               valor=D(valor), forma_pagamento="pix")

    def recebimento(self, mes, valor):
        c = Cobranca.objects.create(matricula=self.mat, tipo="avulsa", descricao=f"R{mes}{valor}",
                                    vencimento=date(self.ano, mes, 10), valor=D(valor))
        c.registrar_pagamento(date(self.ano, mes, 10), "pix")

    def test_series_mensais_kpis_e_resultado(self):
        self.recebimento(1, "1000"); self.recebimento(1, "500"); self.recebimento(3, "800")
        self.despesa(1, "300"); self.despesa(2, "700"); self.despesa(3, "100")
        r = self.client.get(reverse("financeiro_painel") + f"?ano={self.ano}")
        self.assertEqual(r.status_code, 200)
        m = {x["n"]: x for x in r.context["meses"]}
        self.assertEqual((m[1]["receitas"], m[1]["despesas"], m[1]["saldo"]), (D("1500"), D("300"), D("1200")))
        self.assertEqual((m[2]["receitas"], m[2]["despesas"]), (D("0.00"), D("700")))
        self.assertEqual(m[3]["saldo"], D("700"))
        self.assertEqual(r.context["receitas"], D("2300"))
        self.assertEqual(r.context["despesas_total"], D("1100"))
        self.assertEqual(r.context["resultado"], D("1200"))
        self.assertEqual(r.context["n_despesas"], 3)
        self.assertEqual(m[1]["pct_rec"], 100.0)  # o maior valor do ano preenche a barra
        self.assertEqual(m[4]["pct_rec"], 0)

    def test_filtro_por_mes_muda_os_totais_mas_nao_o_grafico_anual(self):
        self.recebimento(1, "1000"); self.recebimento(3, "800")
        self.despesa(1, "300"); self.despesa(3, "100")
        r = self.client.get(reverse("financeiro_painel") + f"?ano={self.ano}&mes=3")
        self.assertEqual((r.context["receitas"], r.context["despesas_total"], r.context["resultado"]),
                         (D("800"), D("100"), D("700")))
        self.assertTrue([x for x in r.context["meses"] if x["n"] == 3][0]["selecionado"])
        self.assertEqual(len(r.context["meses"]), 12)

    def test_categorias_pizza_e_agrupamento_em_outras(self):
        self.despesa(1, "750", self.cat); self.despesa(2, "250", self.cat2)
        r = self.client.get(reverse("financeiro_painel") + f"?ano={self.ano}")
        cats = r.context["categorias"]
        self.assertEqual([c["nome"] for c in cats], ["Material didático e livros", "Aluguel"])
        self.assertEqual([round(float(c["pct"])) for c in cats], [75, 25])
        self.assertIn("0.00% 75.00%", r.context["gradiente"])
        self.assertIn("75.00% 100.00%", r.context["gradiente"])
        # mais de 9 categorias: as menores viram "Outras categorias"
        for i, nome in enumerate(f"Cat{n}" for n in range(12)):
            self.despesa(4, str(10 + i), CategoriaDespesa.objects.create(nome=nome))
        cats = self.client.get(reverse("financeiro_painel") + f"?ano={self.ano}").context["categorias"]
        self.assertEqual(len(cats), 9)
        self.assertEqual(cats[-1]["nome"], "Outras categorias")
        self.assertAlmostEqual(sum(float(c["pct"]) for c in cats), 100.0, places=3)

    def test_html_dos_graficos_usa_numeros_validos_para_css(self):
        self.recebimento(1, "1000"); self.despesa(1, "333.33"); self.despesa(2, "10")
        html = self.client.get(reverse("financeiro_painel") + f"?ano={self.ano}").content.decode()
        for altura in re.findall(r'style="height:([^";]+)%"', html):
            self.assertRegex(altura, r"^\d+\.\d$")  # ponto decimal, nunca vírgula
        self.assertIn("conic-gradient(", html)
        self.assertIn(f"Receitas e despesas por mês — {self.ano}", html)
        self.assertIn("Ver os valores em tabela", html)  # alternativa em texto para o gráfico
        self.assertIn("Maiores gastos", html)

    def test_valores_pequenos_continuam_visiveis(self):
        self.recebimento(1, "100000"); self.despesa(2, "1")
        meses = {x["n"]: x for x in self.client.get(reverse("financeiro_painel") + f"?ano={self.ano}").context["meses"]}
        self.assertGreaterEqual(meses[2]["pct_gas"], 1.5)

    def test_painel_vazio_e_anos_disponiveis(self):
        r = self.client.get(reverse("financeiro_painel"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nenhuma despesa lançada")
        self.assertIn(HOJE.year, r.context["anos"])
        self.assertEqual(self.client.get(reverse("financeiro_painel") + "?ano=lixo&mes=99").status_code, 200)

    def test_relatorio_mensal_traz_despesas_e_resultado(self):
        self.recebimento(HOJE.month, "900")
        Despesa.objects.create(data=HOJE, descricao="Material", categoria=self.cat, valor=D("250"), forma_pagamento="pix")
        r = self.client.get(reverse("relatorio_mensal") + f"?mes={HOJE:%Y-%m}")
        self.assertEqual((r.context["despesas_mes"], r.context["resultado_mes"]), (D("250"), D("650")))
        self.assertContains(r, "Despesas do mês")

    def test_menu_financeiro_abre_o_painel_e_a_lista_de_cobrancas_continua_acessivel(self):
        self.assertContains(self.client.get(reverse("dashboard")), reverse("financeiro_painel"))
        self.assertEqual(self.client.get(reverse("cobranca_list")).status_code, 200)
        self.assertEqual(reverse("cobranca_list"), "/financeiro/cobrancas/")
