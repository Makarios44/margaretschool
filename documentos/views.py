from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_POST

from alunos.models import Aluno
from alunos.utils import filtrar_por_nome
from core.mixins import staff_required
from matriculas.models import Matricula

from . import regras, servicos
from .forms import (
    MESES_NOMES, DeclaracaoFrequenciaForm, DeclaracaoMatriculaForm, FolhaPontoForm, HistoricoForm,
    RegistroEscolarForm, TransferenciaForm, componentes_formset,
)
from .models import DocumentoEmitido, RegistroEscolar

T = DocumentoEmitido.Tipo

# endereço (slug) -> (tipo, formulário, texto de ajuda mostrado ao preencher)
TIPOS = {
    "declaracao-matricula": (T.DECLARACAO_MATRICULA, DeclaracaoMatriculaForm,
                             "Só é possível para matrículas ativas."),
    "declaracao-frequencia": (T.DECLARACAO_FREQUENCIA, DeclaracaoFrequenciaForm,
                              "A frequência é calculada a partir dos dias letivos e das faltas informados."),
    "historico": (T.HISTORICO, HistoricoForm,
                  "Reúne todos os anos do aluno nesta escola, com base nos registros escolares."),
    "transferencia": (T.TRANSFERENCIA, TransferenciaForm,
                      "Acompanha os registros escolares do aluno. Preencha antes o registro escolar do ano em curso."),
}
SLUG_DO_TIPO = {tipo: slug for slug, (tipo, _f, _a) in TIPOS.items()}
TEMPLATE_DO_TIPO = {
    T.DECLARACAO_MATRICULA: "documentos/docs/declaracao_matricula.html",
    T.DECLARACAO_FREQUENCIA: "documentos/docs/declaracao_frequencia.html",
    T.HISTORICO: "documentos/docs/historico.html",
    T.TRANSFERENCIA: "documentos/docs/transferencia.html",
}


def _contexto_tela(extra=None):
    """Contexto da versão em tela (com barra de impressão)."""
    ctx = {"pdf": False, "logo_src": static("img/logo-doc.png"), "pdf_disponivel": servicos.pdf_disponivel()}
    ctx.update(extra or {})
    return ctx


# ---------- registro de documentos emitidos ----------
@staff_required
def documento_list(request):
    qs = DocumentoEmitido.objects.select_related("aluno", "emitido_por")
    q = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "")
    aluno_id = request.GET.get("aluno", "")
    if q:
        qs = filtrar_por_nome(qs, q, "aluno__nome_busca")
    if tipo in T.values:
        qs = qs.filter(tipo=tipo)
    if aluno_id.isdigit():
        qs = qs.filter(aluno_id=int(aluno_id))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "documentos/lista.html", {
        "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")),
        "tipos": T.choices, "f": {"q": q, "tipo": tipo}, "qs": params.urlencode(),
        "aluno_filtrado": Aluno.objects.filter(pk=aluno_id).first() if aluno_id.isdigit() else None,
    })


@staff_required
def documento_emitir(request):
    """Escolha do aluno para emitir um documento."""
    q = request.GET.get("q", "").strip()
    alunos = Aluno.objects.all()
    if q:
        alunos = alunos.buscar(q)
    return render(request, "documentos/emitir.html", {"alunos": alunos[:15], "q": q})


@staff_required
def documento_form(request, slug, aluno_pk):
    if slug not in TIPOS:
        raise Http404
    tipo, Form, ajuda = TIPOS[slug]
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    matriculas = aluno.matriculas.select_related("ano_letivo", "turma")

    if request.method == "POST":
        form = Form(request.POST, aluno=aluno)
        if form.is_valid():
            doc = _emitir(request, tipo, aluno, form.cleaned_data)
            messages.success(request, f"{doc.get_tipo_display()} nº {doc.numero} emitido(a).")
            return redirect("documento_ver", pk=doc.pk)
    else:
        initial = _valores_iniciais(tipo, matriculas.first())
        aviso_freq = ""
        if tipo == T.DECLARACAO_FREQUENCIA and request.GET.get("da_frequencia"):
            aviso_freq = _preencher_da_frequencia(request, aluno, initial)
        form = Form(aluno=aluno, initial=initial)

    avisos = []
    if request.method != "POST" and aviso_freq:
        avisos.append(aviso_freq)
    if tipo in (T.DECLARACAO_MATRICULA, T.DECLARACAO_FREQUENCIA, T.TRANSFERENCIA) and not matriculas:
        avisos.append("Este aluno ainda não tem matrícula.")
    if tipo == T.TRANSFERENCIA:
        avisos.append(
            "Por lei (Lei 9.870/1999, art. 6º), a escola não pode reter documentos escolares por "
            "inadimplência. O sistema não bloqueia a emissão por pendências financeiras."
        )
    return render(request, "documentos/form.html", {
        "form": form, "aluno": aluno, "titulo": T(tipo).label, "ajuda": ajuda, "avisos": avisos,
        "slug": slug,
    })


def _preencher_da_frequencia(request, aluno, initial):
    """Dias letivos e faltas vindos da frequência diária (período e matrícula passados na consulta)."""
    from frequencia import servicos as freq

    mat = aluno.matriculas.filter(pk=request.GET.get("matricula") or 0).first()
    try:
        ini = date.fromisoformat(request.GET.get("periodo_inicio", ""))
        fim = date.fromisoformat(request.GET.get("periodo_fim", ""))
    except ValueError:
        return ""
    if not mat or ini > fim:
        return ""
    r = freq.resumo_matricula(mat, ini, fim)
    initial.update({"matricula": mat.pk, "periodo_inicio": ini, "periodo_fim": fim})
    if not r["dias"]:
        return "Não há chamadas registradas nesse período; informe os dias letivos e as faltas manualmente."
    initial.update({"dias_letivos": r["dias"], "faltas": r["faltas"]})
    return (f"Dias letivos ({r['dias']}) e faltas ({r['faltas']}) preenchidos a partir da frequência diária. "
            "Confira antes de emitir.")


def _valores_iniciais(tipo, matricula):
    hoje = date.today()
    if tipo == T.DECLARACAO_FREQUENCIA and matricula:
        ini = date(matricula.ano_letivo.ano, 1, 1)
        initial = {"periodo_inicio": min(ini, hoje), "periodo_fim": hoje, "matricula": matricula.pk}
        reg = getattr(matricula, "registro", None)
        if reg and reg.dias_letivos is not None:
            initial.update({"dias_letivos": reg.dias_letivos, "faltas": reg.faltas or 0})
        return initial
    if tipo == T.TRANSFERENCIA:
        return {"data_saida": hoje, "marcar_transferido": True}
    return {}


@transaction.atomic
def _emitir(request, tipo, aluno, d):
    usuario = request.user
    m = d.get("matricula")
    if tipo == T.DECLARACAO_MATRICULA:
        conteudo = servicos.construir_declaracao_matricula(m, d["finalidade"])
    elif tipo == T.DECLARACAO_FREQUENCIA:
        conteudo = servicos.construir_declaracao_frequencia(
            m, d["periodo_inicio"], d["periodo_fim"], d["dias_letivos"], d["faltas"], d["observacoes"])
    elif tipo == T.HISTORICO:
        conteudo = servicos.construir_historico(aluno, d["observacoes"])
    else:  # transferência: atualiza a situação antes, para o documento refletir o estado final
        if d["marcar_transferido"] and m.situacao == Matricula.Situacao.ATIVO:
            m.situacao = Matricula.Situacao.TRANSFERIDO
            m.save(update_fields=["situacao"])
            RegistroEscolar.objects.filter(matricula=m).update(
                resultado=RegistroEscolar.Resultado.TRANSFERIDO)
        m = Matricula.objects.select_related("ano_letivo", "turma", "aluno").get(pk=m.pk)
        conteudo = servicos.construir_transferencia(
            m, d["data_saida"], d["escola_destino"], d["motivo"], d["observacoes"])
    return DocumentoEmitido.emitir(tipo, aluno, conteudo, usuario=usuario, matricula=m)


# ---------- visualização / impressão / PDF ----------
def _ctx_documento(doc, pdf=False):
    escola = doc.conteudo["escola"]
    ctx = {"doc": doc, "c": doc.conteudo, "esc": escola, "pendencias": regras.escola_pendencias(escola)}
    ctx.update(servicos.contexto_pdf() if pdf else _contexto_tela())
    return ctx


@staff_required
def documento_ver(request, pk):
    doc = get_object_or_404(DocumentoEmitido.objects.select_related("aluno", "emitido_por"), pk=pk)
    return render(request, TEMPLATE_DO_TIPO[doc.tipo], _ctx_documento(doc))


@staff_required
def documento_pdf(request, pk):
    if not servicos.pdf_disponivel():
        messages.error(request, "O download direto de PDF não está instalado. Use Imprimir → Salvar como PDF.")
        return redirect("documento_ver", pk=pk)
    doc = get_object_or_404(DocumentoEmitido.objects.select_related("aluno", "emitido_por"), pk=pk)
    pdf = servicos.renderizar_pdf(TEMPLATE_DO_TIPO[doc.tipo], _ctx_documento(doc, pdf=True), request)
    nome = f"{SLUG_DO_TIPO[doc.tipo]}-{doc.ano}-{doc.sequencial:04d}.pdf"
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resp


@staff_required
@require_POST
def documento_anular(request, pk):
    doc = get_object_or_404(DocumentoEmitido, pk=pk)
    motivo = request.POST.get("motivo", "").strip()
    if doc.anulado:
        messages.error(request, "Este documento já está anulado.")
    elif not motivo:
        messages.error(request, "Informe o motivo da anulação.")
    else:
        doc.anulado, doc.anulado_em, doc.anulado_motivo = True, timezone.now(), motivo[:200]
        doc.save(update_fields=["anulado", "anulado_em", "anulado_motivo"])
        messages.success(request, f"Documento {doc.numero} anulado.")
    return redirect("documento_ver", pk=pk)


# ---------- ficha individual do aluno (sempre com dados atuais) ----------
def _ctx_ficha(aluno, pdf=False):
    escola = servicos.dados_escola()
    matriculas = aluno.matriculas.select_related("ano_letivo", "turma").prefetch_related("documentos")
    ctx = {
        "aluno": aluno, "esc": escola, "matriculas": matriculas, "atual": matriculas.first(),
        "responsaveis": aluno.responsaveis.all(), "contatos": aluno.contatos_emergencia.all(),
        "agora": timezone.localtime(), "pendencias": regras.escola_pendencias(escola),
    }
    if pdf:
        ctx.update(servicos.contexto_pdf(aluno))
    else:
        ctx.update(_contexto_tela({"foto_src": aluno.foto.url if aluno.foto else ""}))
    return ctx


@staff_required
def ficha_individual(request, aluno_pk):
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    return render(request, "documentos/ficha_individual.html", _ctx_ficha(aluno))


@staff_required
def ficha_individual_pdf(request, aluno_pk):
    aluno = get_object_or_404(Aluno, pk=aluno_pk)
    if not servicos.pdf_disponivel():
        messages.error(request, "O download direto de PDF não está instalado. Use Imprimir → Salvar como PDF.")
        return redirect("ficha_individual", aluno_pk=aluno.pk)
    pdf = servicos.renderizar_pdf("documentos/ficha_individual.html", _ctx_ficha(aluno, pdf=True), request)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="ficha-individual-{aluno.pk}.pdf"'
    return resp


# ---------- registro escolar (frequência, resultado, parecer, componentes) ----------
@staff_required
def registro_escolar(request, matricula_pk):
    m = get_object_or_404(Matricula.objects.select_related("aluno", "ano_letivo", "turma"), pk=matricula_pk)
    registro = RegistroEscolar.objects.filter(matricula=m).first() or RegistroEscolar(matricula=m)
    fundamental = not regras.eh_infantil(m.etapa)
    data = request.POST or None

    inicial, aviso_freq = {}, ""
    if request.method == "GET" and request.GET.get("da_frequencia"):
        from frequencia import servicos as freq

        ini = m.ano_letivo.inicio_aulas or date(m.ano_letivo.ano, 1, 1)
        fim = min(m.ano_letivo.fim_aulas or date(m.ano_letivo.ano, 12, 31), date.today())
        r = freq.resumo_matricula(m, ini, max(fim, ini))
        if r["dias"]:
            inicial = {"dias_letivos": r["dias"], "faltas": r["faltas"]}
            aviso_freq = (f"Preenchido pela frequência diária: {r['dias']} dias com chamada e {r['faltas']} falta(s). "
                          "Confira e salve para gravar no registro.")
        else:
            aviso_freq = "Não há chamadas registradas neste ano para esta matrícula."
    form = RegistroEscolarForm(data, instance=registro, etapa=m.etapa, initial=inicial)
    if fundamental:
        sugerir = not registro.pk or not registro.componentes.exists()
        Formset = componentes_formset(extra=len(regras.COMPONENTES_SUGERIDOS) if sugerir else 0)
        initial = [{"nome": n} for n in regras.COMPONENTES_SUGERIDOS] if (sugerir and not data) else None
        comps = Formset(data, instance=registro, prefix="comp", initial=initial)
    else:
        comps = None

    if request.method == "POST":
        if all([form.is_valid(), comps.is_valid() if comps else True]):
            with transaction.atomic():
                registro = form.save()
                if comps:
                    comps.instance = registro
                    comps.save()
            messages.success(request, "Registro escolar salvo.")
            return redirect("matricula_detail", pk=m.pk)
        messages.error(request, "Revise os campos destacados e tente de novo.")

    return render(request, "documentos/registro_escolar.html", {
        "m": m, "form": form, "comps": comps, "fundamental": fundamental,
        "minimo": regras.frequencia_minima(m.etapa), "base_minimo": regras.BASE_FREQUENCIA.get(m.etapa, ""),
        "nota_infantil": regras.NOTA_INFANTIL if not fundamental else "",
        "frequencia": registro.frequencia, "aviso_freq": aviso_freq,
    })


# ---------- folha de ponto dos professores ----------
def _consulta_folha(dados):
    """Querystring estável a partir dos dados validados (para a impressão e o PDF)."""
    pares = [("professores", "\n".join(dados["professores"])), ("mes", dados["mes"]), ("ano", dados["ano"]),
             ("cargo", dados["cargo"]), ("turma_disciplina", dados["turma_disciplina"]),
             ("horario", dados["horario"]), ("carga_semanal", dados["carga_semanal"])]
    if dados["marcar_feriados"]:
        pares.append(("marcar_feriados", "on"))
    if dados["sabados"]:
        pares.append(("sabados", "on"))
    return urlencode(pares)


@staff_required
def folha_ponto_form(request):
    hoje = date.today()
    if request.method == "POST":
        form = FolhaPontoForm(request.POST)
        if form.is_valid():
            return redirect(reverse("folha_ponto_imprimir") + "?" + _consulta_folha(form.cleaned_data))
    else:
        form = FolhaPontoForm(initial={"mes": hoje.month, "ano": hoje.year, "cargo": "Professor(a)",
                                       "marcar_feriados": True})
    return render(request, "documentos/folha_ponto_form.html", {"form": form})


def _ctx_folha(request, pdf=False):
    dados = request.GET.copy()
    # a caixa desmarcada simplesmente não vem na consulta
    dados.setdefault("marcar_feriados", "")
    form = FolhaPontoForm(dados)
    if not form.is_valid():
        return None, form
    d = form.cleaned_data
    linhas = servicos.dias_do_mes_para_ponto(d["ano"], d["mes"], d["marcar_feriados"], d["sabados"])
    ctx = {
        "esc": servicos.dados_escola(), "professores": d["professores"], "cargo": d["cargo"] or "Professor(a)",
        "turma_disciplina": d["turma_disciplina"], "horario": d["horario"], "carga_semanal": d["carga_semanal"],
        "mes_nome": MESES_NOMES[d["mes"] - 1], "ano": str(d["ano"]), "linhas": linhas,
        "consulta": _consulta_folha(d), "pendencias": [],
    }
    ctx.update(servicos.contexto_pdf() if pdf else _contexto_tela())
    return ctx, form


@staff_required
def folha_ponto_imprimir(request):
    ctx, form = _ctx_folha(request)
    if ctx is None:
        messages.error(request, "Revise os dados da folha de ponto.")
        return redirect("folha_ponto_form")
    return render(request, "documentos/folha_ponto.html", ctx)


@staff_required
def folha_ponto_pdf(request):
    if not servicos.pdf_disponivel():
        messages.error(request, "O download direto de PDF não está instalado. Use Imprimir → Salvar como PDF.")
        return redirect(reverse("folha_ponto_imprimir") + "?" + request.META.get("QUERY_STRING", ""))
    ctx, form = _ctx_folha(request, pdf=True)
    if ctx is None:
        messages.error(request, "Revise os dados da folha de ponto.")
        return redirect("folha_ponto_form")
    pdf = servicos.renderizar_pdf("documentos/folha_ponto.html", ctx, request)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="folha-de-ponto-{ctx["ano"]}-{request.GET.get("mes", "").zfill(2)}.pdf"'
    return resp
