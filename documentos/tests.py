from datetime import date, timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from alunos.models import Aluno, ContatoEmergencia, Responsavel
from financeiro.models import Cobranca
from matriculas.models import AnoLetivo, Matricula, Turma

from . import servicos
from .models import ComponenteRegistro, DocumentoEmitido, RegistroEscolar

HOJE = date.today()
ESCOLA = {
    "nome": "Margaret School", "cnpj": "12.345.678/0001-90", "inep": "24000000",
    "mantenedora": "Margaret Educação Ltda.", "endereco": "Rua das Flores, 100, Centro",
    "cidade": "Natal/RN", "telefone": "(84) 3000-0000",
    "ato_autorizacao": "Credenciada pelo CME, Resolução nº 10/2020",
    "diretor": "Maria Diretora", "diretor_ato": "Portaria 1/2020",
    "secretario": "João Secretário", "secretario_ato": "Portaria 2/2020",
}


@override_settings(ESCOLA=ESCOLA)
class Base(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("sec", password="x", is_staff=True, first_name="Sec")
        self.client.force_login(self.staff)
        self.ano = AnoLetivo.objects.create(ano=HOJE.year, atual=True)
        self.turma = Turma.objects.create(nome="Jardim II", ano_letivo=self.ano, turno="manha", etapa="infantil_pre")
        self.turma_f = Turma.objects.create(nome="1º Ano", ano_letivo=self.ano, turno="tarde", etapa="fundamental_iniciais")
        self.aluno = Aluno.objects.create(
            nome="Pedro Lima", data_nascimento=date(2020, 5, 1), naturalidade="Natal/RN",
            certidao_nascimento="123456")
        Responsavel.objects.create(aluno=self.aluno, nome="Ana Lima", parentesco="mae", telefone="1",
                                   responsavel_financeiro=True)
        Responsavel.objects.create(aluno=self.aluno, nome="Carlos Lima", parentesco="pai", telefone="2")
        ContatoEmergencia.objects.create(aluno=self.aluno, nome="Rita", parentesco="tia", telefone="3")
        self.mat = self.matricular(self.aluno, self.turma)

    def matricular(self, aluno, turma, **kw):
        dados = dict(aluno=aluno, ano_letivo=turma.ano_letivo, turma=turma, mensalidade=D("600"),
                     data_matricula=date(turma.ano_letivo.ano, 1, 10))
        dados.update(kw)
        return Matricula.objects.create(**dados)

    def emitir(self, slug, **dados):
        r = self.client.post(reverse("documento_form", args=[slug, self.aluno.pk]), dados)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        return DocumentoEmitido.objects.latest("id")


@override_settings(ESCOLA=ESCOLA)
class EmissaoTests(Base):
    def test_declaracao_matricula(self):
        doc = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="benefício social")
        self.assertEqual(doc.numero, f"{HOJE.year}/0001")
        r = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(r, "PEDRO LIMA")
        self.assertContains(r, "filho(a) de Carlos Lima e Ana Lima")
        self.assertContains(r, "Educação Infantil — Pré-escola")
        self.assertContains(r, "para fins de benefício social")
        self.assertContains(r, "Maria Diretora")
        self.assertContains(r, "Credenciada pelo CME")
        self.assertNotContains(r, "faltam dados oficiais")
        self.assertContains(r, f"ano letivo de <strong>{HOJE.year}</strong>")  # sem separador de milhar
        self.assertNotContains(r, f"{HOJE.year // 1000}.{HOJE.year % 1000}")
        self.assertRegex(r.content.decode(), r"Natal/RN, \d{1,2} de [a-zç]+ de \d{4}\.")  # mês em minúsculas

    def test_numeracao_sequencial(self):
        a = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        b = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        self.assertEqual((a.sequencial, b.sequencial), (1, 2))

    def test_conteudo_congelado(self):
        doc = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        self.aluno.nome = "Outro Nome"
        self.aluno.save()
        Turma.objects.filter(pk=self.turma.pk).update(nome="Turma Nova")
        with override_settings(ESCOLA={**ESCOLA, "diretor": "Nova Direção"}):
            r = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(r, "PEDRO LIMA")
        self.assertContains(r, "Jardim II")
        self.assertContains(r, "Maria Diretora")
        self.assertNotContains(r, "Nova Direção")

    def test_declaracao_matricula_so_para_ativa(self):
        Matricula.objects.filter(pk=self.mat.pk).update(situacao="cancelado")
        r = self.client.post(reverse("documento_form", args=["declaracao-matricula", self.aluno.pk]),
                             {"matricula": self.mat.pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DocumentoEmitido.objects.count(), 0)

    def test_declaracao_frequencia_calculo_e_validacoes(self):
        base = {"matricula": self.mat.pk, "periodo_inicio": f"{HOJE.year}-01-10",
                "periodo_fim": HOJE.isoformat(), "dias_letivos": "80", "faltas": "6"}
        doc = self.emitir("declaracao-frequencia", **base)
        self.assertEqual(doc.conteudo["frequencia"], "92,5")
        self.assertEqual(doc.conteudo["presencas"], 74)
        r = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(r, "92,5%")
        url = reverse("documento_form", args=["declaracao-frequencia", self.aluno.pk])
        ruim = self.client.post(url, {**base, "faltas": "99"})
        self.assertContains(ruim, "não podem ser maiores")
        ruim = self.client.post(url, {**base, "periodo_fim": (HOJE + timedelta(days=3)).isoformat()})
        self.assertContains(ruim, "não pode terminar no futuro")
        ruim = self.client.post(url, {**base, "periodo_inicio": HOJE.isoformat(),
                                      "periodo_fim": (HOJE - timedelta(days=5)).isoformat()})
        self.assertContains(ruim, "depois do início")

    def test_historico_infantil_e_fundamental(self):
        RegistroEscolar.objects.create(matricula=self.mat, dias_letivos=200, faltas=10,
                                       carga_horaria=800, resultado="concluido", parecer="Brinca e interage bem.")
        doc = self.emitir("historico", observacoes="")
        self.assertEqual(doc.conteudo["titulo"], "Ficha de registros escolares — Educação Infantil")
        r = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(r, "Brinca e interage bem.")
        self.assertContains(r, "95,0%")
        self.assertContains(r, "sem objetivo de promoção")
        # com matrícula no fundamental vira histórico escolar, com componentes
        ano_antes = AnoLetivo.objects.create(ano=HOJE.year + 1)
        tf = Turma.objects.create(nome="1º Ano", ano_letivo=ano_antes, turno="tarde", etapa="fundamental_iniciais")
        mf = self.matricular(self.aluno, tf)
        reg = RegistroEscolar.objects.create(matricula=mf, resultado="aprovado", dias_letivos=200, faltas=20)
        ComponenteRegistro.objects.create(registro=reg, nome="Matemática", resultado="8,5", carga_horaria=160)
        doc2 = self.emitir("historico", observacoes="")
        self.assertEqual(doc2.conteudo["titulo"], "Histórico escolar")
        r = self.client.get(reverse("documento_ver", args=[doc2.pk]))
        self.assertContains(r, "Matemática")
        self.assertContains(r, "8,5")
        self.assertContains(r, "Aprovado(a)")

    def test_transferencia_marca_situacao_e_nao_bloqueia_por_inadimplencia(self):
        Cobranca.objects.create(matricula=self.mat, tipo="avulsa", descricao="Atrasada",
                                vencimento=HOJE - timedelta(days=60), valor=D("600"))
        RegistroEscolar.objects.create(matricula=self.mat, dias_letivos=100, faltas=5, resultado="em_curso")
        r = self.client.get(reverse("documento_form", args=["transferencia", self.aluno.pk]))
        self.assertContains(r, "não pode reter documentos escolares")
        doc = self.emitir("transferencia", matricula=self.mat.pk, data_saida=HOJE.isoformat(),
                          escola_destino="Colégio Novo", motivo="mudança de cidade", marcar_transferido="on")
        self.mat.refresh_from_db()
        self.assertEqual(self.mat.situacao, "transferido")
        self.assertEqual(self.mat.registro.resultado, "transferido")
        ver = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(ver, "transferido(a) em")
        self.assertContains(ver, "Colégio Novo")
        self.assertContains(ver, "Registros escolares")

    def test_transferencia_sem_marcar_nao_altera_matricula(self):
        self.emitir("transferencia", matricula=self.mat.pk, data_saida=HOJE.isoformat())
        self.mat.refresh_from_db()
        self.assertEqual(self.mat.situacao, "ativo")

    def test_anulacao(self):
        doc = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        url = reverse("documento_anular", args=[doc.pk])
        self.client.post(url, {"motivo": ""})
        doc.refresh_from_db()
        self.assertFalse(doc.anulado)
        self.client.post(url, {"motivo": "Emitido com erro"})
        doc.refresh_from_db()
        self.assertTrue(doc.anulado)
        r = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(r, "ANULADO")
        self.assertContains(r, "Emitido com erro")
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_aviso_de_dados_oficiais_pendentes(self):
        doc = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        doc.conteudo["escola"]["ato_autorizacao"] = ""
        doc.conteudo["escola"]["secretario"] = ""
        doc.save()
        r = self.client.get(reverse("documento_ver", args=[doc.pk]))
        self.assertContains(r, "faltam dados oficiais")
        self.assertContains(r, "ato de credenciamento/autorização")


@override_settings(ESCOLA=ESCOLA)
class RegistroEscolarTests(Base):
    def test_infantil_nao_aceita_aprovacao_nem_retencao(self):
        url = reverse("registro_escolar", args=[self.mat.pk])
        r = self.client.get(url)
        self.assertNotContains(r, 'value="aprovado"')
        self.assertNotContains(r, 'value="retido"')
        self.assertNotContains(r, "Componentes curriculares")
        r = self.client.post(url, {"dias_letivos": 200, "faltas": 5, "resultado": "aprovado"})
        self.assertEqual(r.status_code, 200)  # recusado
        self.assertFalse(RegistroEscolar.objects.exists())
        r = self.client.post(url, {"dias_letivos": 200, "faltas": 5, "resultado": "concluido",
                                   "parecer": "Ótimo ano."})
        self.assertEqual(r.status_code, 302)
        reg = RegistroEscolar.objects.get()
        self.assertEqual(str(reg.frequencia), "97.5")

    def test_faltas_maiores_que_dias(self):
        r = self.client.post(reverse("registro_escolar", args=[self.mat.pk]),
                             {"dias_letivos": 10, "faltas": 11, "resultado": "em_curso"})
        self.assertContains(r, "não podem ser maiores")

    def test_fundamental_com_componentes(self):
        aluno = Aluno.objects.create(nome="Bia", data_nascimento=date(2018, 3, 3))
        m = self.matricular(aluno, self.turma_f)
        url = reverse("registro_escolar", args=[m.pk])
        r = self.client.get(url)
        self.assertContains(r, "Língua Portuguesa")  # sugestão inicial
        self.assertContains(r, 'value="aprovado"')
        dados = {
            "dias_letivos": 200, "faltas": 10, "resultado": "aprovado", "carga_horaria": 800,
            "comp-TOTAL_FORMS": 2, "comp-INITIAL_FORMS": 0, "comp-MIN_NUM_FORMS": 0, "comp-MAX_NUM_FORMS": 1000,
            "comp-0-nome": "Matemática", "comp-0-carga_horaria": 160, "comp-0-resultado": "9,0",
            "comp-1-nome": "História", "comp-1-carga_horaria": 80, "comp-1-resultado": "8,0",
        }
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(m.registro.componentes.count(), 2)
        # editar de novo não sugere componentes de novo
        self.assertNotContains(self.client.get(url), "Língua Portuguesa")


@override_settings(ESCOLA=ESCOLA)
class OutrosTests(Base):
    def test_ficha_individual(self):
        r = self.client.get(reverse("ficha_individual", args=[self.aluno.pk]))
        self.assertContains(r, "Natal/RN")
        self.assertContains(r, "Ana Lima")
        self.assertContains(r, "Rita")
        self.assertContains(r, "Jardim II")
        self.assertContains(r, "Certidão de nascimento da criança")

    def test_lista_emitir_e_filtros(self):
        self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        r = self.client.get(reverse("documento_list") + f"?aluno={self.aluno.pk}")
        self.assertContains(r, "Pedro Lima")
        r = self.client.get(reverse("documento_list") + "?tipo=historico")
        self.assertNotContains(r, "Pedro Lima")
        r = self.client.get(reverse("documento_emitir") + "?q=pedro")
        self.assertContains(r, "Declaração de frequência")
        self.assertEqual(self.client.get(reverse("documento_form", args=["inexistente", self.aluno.pk])).status_code, 404)

    def test_pdf(self):
        doc = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        r = self.client.get(reverse("documento_pdf", args=[doc.pk]))
        if servicos.pdf_disponivel():
            self.assertEqual(r["Content-Type"], "application/pdf")
            self.assertTrue(r.content.startswith(b"%PDF"))
            self.assertIn("declaracao-matricula-", r["Content-Disposition"])
            f = self.client.get(reverse("ficha_individual_pdf", args=[self.aluno.pk]))
            self.assertTrue(f.content.startswith(b"%PDF"))
        else:
            self.assertEqual(r.status_code, 302)

    def test_somente_equipe(self):
        doc = self.emitir("declaracao-matricula", matricula=self.mat.pk, finalidade="")
        self.client.force_login(get_user_model().objects.create_user("pai", password="x"))
        alvos = [("documento_list", []), ("documento_emitir", []), ("documento_ver", [doc.pk]),
                 ("documento_pdf", [doc.pk]), ("ficha_individual", [self.aluno.pk]),
                 ("registro_escolar", [self.mat.pk]),
                 ("documento_form", ["historico", self.aluno.pk])]
        for nome, args in alvos:
            self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 403, nome)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("documento_list")).status_code, 302)


# ===================== Folha de ponto =====================
import calendar as _calendar  # noqa: E402
import re as _re  # noqa: E402
from urllib.parse import urlencode  # noqa: E402

from calendario.models import Evento  # noqa: E402


@override_settings(ESCOLA=ESCOLA)
class FolhaPontoTests(Base):
    def consulta(self, **kw):
        dados = [("professores", "Maria das Dores"), ("mes", 10), ("ano", 2026), ("cargo", "Professor(a)"),
                 ("marcar_feriados", "on")]
        for k, v in kw.items():
            dados = [(a, b) for a, b in dados if a != k]
            if v is not None:
                dados.append((k, v))
        return urlencode(dados)

    def abrir(self, **kw):
        return self.client.get(reverse("folha_ponto_imprimir") + "?" + self.consulta(**kw))

    def test_formulario_valida_e_redireciona_para_a_impressao(self):
        url = reverse("folha_ponto_form")
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"professores": "  Ana   Souza \n\nJoão Lima\nana souza", "mes": 2, "ano": 2028,
                                   "cargo": "", "marcar_feriados": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("folha_ponto_imprimir") + "?"))
        pagina = self.client.get(r["Location"])
        self.assertEqual(pagina.context["professores"], ["Ana Souza", "João Lima"])  # limpa espaços e repetidos
        self.assertEqual(pagina.context["cargo"], "Professor(a)")
        ruim = self.client.post(url, {"professores": "  \n ", "mes": 2, "ano": 2028})
        self.assertContains(ruim, "campo é obrigatório")
        self.assertContains(self.client.post(url, {"professores": "A", "mes": 13, "ano": 2028}), "Faça uma escolha válida")
        self.assertContains(self.client.post(url, {"professores": "A", "mes": 1, "ano": 1900}), "maior ou igual")
        muitos = "\n".join(f"Prof {i}" for i in range(41))
        self.assertContains(self.client.post(url, {"professores": muitos, "mes": 1, "ano": 2026}), "no máximo 40")

    def test_uma_linha_por_dia_do_mes(self):
        for ano, mes in [(2028, 2), (2027, 2), (2026, 10), (2026, 4)]:
            r = self.abrir(ano=ano, mes=mes)
            self.assertEqual(len(r.context["linhas"]), _calendar.monthrange(ano, mes)[1], (ano, mes))
        self.assertContains(self.abrir(ano=2028, mes=2), "Folha de ponto — Fevereiro de 2028")
        self.assertContains(self.abrir(), "Maria das Dores")

    def test_fim_de_semana_marcado_e_sabado_letivo_opcional(self):
        linhas = {l["dia"]: l for l in self.abrir().context["linhas"]}  # outubro/2026: dia 3 é sábado
        self.assertEqual((linhas[3]["rotulo"], linhas[4]["rotulo"]), ("Sábado", "Domingo"))
        self.assertTrue(linhas[3]["fechado"] and linhas[4]["fechado"])
        self.assertEqual((linhas[5]["rotulo"], linhas[5]["fechado"]), ("", False))
        aberto = {l["dia"]: l for l in self.abrir(sabados="on").context["linhas"]}
        self.assertFalse(aberto[3]["fechado"])  # sábado para preencher
        self.assertTrue(aberto[4]["fechado"])  # domingo continua marcado

    def test_feriados_e_recesso_do_calendario_aparecem_marcados(self):
        Evento.objects.create(titulo="Nossa Senhora Aparecida", categoria="feriado_nacional", sem_aula=True,
                              data_inicio=date(2026, 10, 12))
        Evento.objects.create(titulo="Recesso de outubro", categoria="recesso", sem_aula=True,
                              data_inicio=date(2026, 10, 20), data_fim=date(2026, 10, 21))
        Evento.objects.create(titulo="Reunião de pais", categoria="reuniao_pais", data_inicio=date(2026, 10, 14))
        Evento.objects.create(titulo="Feriado só do Jardim", categoria="feriado_municipal", sem_aula=True,
                              data_inicio=date(2026, 10, 15))
        outro = Evento.objects.get(titulo="Feriado só do Jardim")
        outro.turmas.add(Turma.objects.create(nome="J", ano_letivo=self.ano, turno="manha"))
        linhas = {l["dia"]: l for l in self.abrir().context["linhas"]}
        self.assertEqual(linhas[12]["rotulo"], "Feriado: Nossa Senhora Aparecida")
        self.assertTrue(linhas[12]["fechado"])
        self.assertEqual(linhas[20]["rotulo"], "Recesso: Recesso de outubro")
        self.assertEqual(linhas[21]["rotulo"], "Recesso: Recesso de outubro")
        self.assertFalse(linhas[14]["fechado"])  # evento comum não fecha o dia
        self.assertFalse(linhas[15]["fechado"])  # evento de turma específica não vale para todos
        sem = {l["dia"]: l for l in self.abrir(marcar_feriados=None).context["linhas"]}
        self.assertEqual(sem[12]["rotulo"], "")
        self.assertContains(self.abrir(), "Feriado: Nossa Senhora Aparecida")

    def test_uma_folha_por_professor(self):
        r = self.abrir(professores="Ana\nBruno\nCarla")
        html = r.content.decode()
        self.assertEqual(html.count('class="doc doc-compacto folha-ponto"'), 3)
        for nome in ("Ana", "Bruno", "Carla"):
            self.assertIn(f"<strong>{nome}</strong>", html)

    def test_cabecalho_da_escola_e_dados_opcionais(self):
        r = self.abrir(horario="07:30 às 11:30", carga_semanal="20 h", turma_disciplina="Jardim II")
        for texto in ("Margaret School", "07:30 às 11:30", "20 h", "Jardim II", "Maria Diretora", "Total de horas no mês"):
            self.assertContains(r, texto)

    def test_nome_com_html_e_escapado(self):
        r = self.abrir(professores="<script>alert(1)</script>")
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")

    def test_consulta_invalida_volta_ao_formulario(self):
        r = self.client.get(reverse("folha_ponto_imprimir") + "?mes=99")
        self.assertRedirects(r, reverse("folha_ponto_form"))

    def test_pdf_uma_pagina_por_professor(self):
        r = self.client.get(reverse("folha_ponto_pdf") + "?" + self.consulta(professores="Ana\nBruno"))
        if servicos.pdf_disponivel():
            self.assertTrue(r.content.startswith(b"%PDF"))
            import shutil as _shutil
            import subprocess as _subprocess
            import tempfile as _tempfile

            if _shutil.which("pdfinfo"):  # confere: 2 professores = 2 páginas
                with _tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                    f.write(r.content); f.flush()
                    saida = _subprocess.run(["pdfinfo", f.name], capture_output=True, text=True).stdout
                self.assertRegex(saida, r"Pages:\s+2")
            self.assertIn("folha-de-ponto-2026-10", r["Content-Disposition"])
        else:
            self.assertEqual(r.status_code, 302)

    def test_somente_equipe_e_atalho_na_lista_de_documentos(self):
        self.assertContains(self.client.get(reverse("documento_list")), reverse("folha_ponto_form"))
        self.client.force_login(get_user_model().objects.create_user("pai", password="x"))
        for nome in ("folha_ponto_form", "folha_ponto_imprimir", "folha_ponto_pdf"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 403, nome)
