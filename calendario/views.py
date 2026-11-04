import calendar
from collections import defaultdict
from datetime import date, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_POST

from administracao import configuracao
from core.formatos import MESES
from core.mixins import staff_required
from documentos import servicos as doc_servicos
from matriculas.models import AnoLetivo, Turma

from . import feriados, servicos
from .forms import AnoLetivoConfigForm, EventoForm, PeriodoFormSet
from .ics import gerar_ics
from .models import PRIORIDADE, SEM_AULA_PADRAO, Categoria, Evento

NOMES_MES = [m.capitalize() for m in MESES]
DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
ROTULOS = dict(Categoria.choices) | {"aniversario": "Aniversário de aluno"}


def _interno(request):
    return request.user.is_authenticated and request.user.is_staff


def _ano_valido(ano):
    if not 1990 <= ano <= 2100:
        raise Http404


def _mes_vizinho(ano, mes, delta):
    total = ano * 12 + (mes - 1) + delta
    return total // 12, total % 12 + 1


# ---------- visões públicas ----------
def calendario_mes(request, ano=None, mes=None):
    hoje = date.today()
    ano, mes = ano or hoje.year, mes or hoje.month
    _ano_valido(ano)
    if not 1 <= mes <= 12:
        raise Http404
    interno = _interno(request)
    cats = [c for c in request.GET.getlist("cat") if c in Categoria.values]
    turma_id = int(request.GET["turma"]) if request.GET.get("turma", "").isdigit() else None
    aniv = interno and request.GET.get("aniv") == "1"

    semanas = servicos.montar_mes(ano, mes, interno, cats or None, turma_id, aniv)
    presentes = servicos.categorias_presentes(semanas)
    agenda = [(d["data"], d["eventos"]) for sem in semanas for d in sem if d["no_mes"] and d["eventos"]]

    ano_letivo = AnoLetivo.objects.filter(ano=ano).first()
    letivos_mes = servicos.contagem_mensal(ano_letivo).get((ano, mes))

    filtros = request.GET.copy()
    filtros.pop("page", None)
    ant, prox = _mes_vizinho(ano, mes, -1), _mes_vizinho(ano, mes, 1)
    return render(request, "calendario/mes.html", {
        "ano": ano, "mes": mes, "nome_mes": NOMES_MES[mes - 1], "semanas": semanas, "dias_semana": DIAS_SEMANA,
        "agenda": agenda, "legenda": sorted(presentes, key=lambda c: PRIORIDADE.get(c, 99)), "rotulos": ROTULOS,
        "anterior": ant, "proximo": prox, "filtros": filtros.urlencode(),
        "categorias": Categoria.choices, "turmas": Turma.objects.select_related("ano_letivo"),
        "sel": {"cats": cats, "turma": turma_id, "aniv": aniv}, "interno": interno,
        "letivos_mes": letivos_mes, "e_hoje": (ano, mes) == (hoje.year, hoje.month),
        "ics_url": request.build_absolute_uri(reverse("calendario_ics")),
    })


def _montar_ano(ano, interno):
    eventos = servicos.eventos_entre(date(ano, 1, 1), date(ano, 12, 31), interno)
    por_dia = defaultdict(list)
    for ev in eventos:
        for d in ev.dias():
            if d.year == ano:
                por_dia[d].append(ev)
    cal = calendar.Calendar(firstweekday=6)
    meses = []
    for m in range(1, 13):
        semanas = []
        for sem in cal.monthdayscalendar(ano, m):
            linha = []
            for i, n in enumerate(sem):
                if not n:
                    linha.append(None)
                    continue
                evs = por_dia.get(date(ano, m, n), [])
                principal = min(evs, key=lambda e: PRIORIDADE.get(e.categoria, 99)).categoria if evs else ""
                linha.append({"n": n, "cat": principal, "fds": i in (0, 6),
                              "titulo": "; ".join(e.titulo for e in evs)})
            semanas.append(linha)
        meses.append({"nome": NOMES_MES[m - 1], "mes": m, "semanas": semanas})
    relacao = defaultdict(list)
    for ev in eventos:
        if ev.categoria != Categoria.COMEMORATIVA:
            relacao[ev.data_inicio.month].append(ev)
    presentes = sorted({e.categoria for e in eventos}, key=lambda c: PRIORIDADE.get(c, 99))
    return {
        "meses": meses, "legenda": presentes, "rotulos": ROTULOS,
        "relacao": [(NOMES_MES[m - 1], relacao[m]) for m in range(1, 13) if relacao.get(m)],
        "dias_semana": ["D", "S", "T", "Q", "Q", "S", "S"],
    }


def calendario_ano(request, ano):
    _ano_valido(ano)
    ctx = _montar_ano(ano, _interno(request))
    ctx.update({"ano": ano, "interno": _interno(request)})
    return render(request, "calendario/ano.html", ctx)


def calendario_agenda(request):
    interno = _interno(request)
    hoje = date.today()
    eventos = servicos.eventos_entre(hoje, hoje + timedelta(days=120), interno)
    eventos = [e for e in eventos if e.categoria != Categoria.COMEMORATIVA]
    eventos.sort(key=lambda e: (max(e.data_inicio, hoje), e.hora_inicio or time(0)))
    return render(request, "calendario/agenda.html", {"eventos": eventos, "rotulos": ROTULOS, "interno": interno})


def evento_detail(request, pk):
    ev = get_object_or_404(Evento.objects.prefetch_related("turmas"), pk=pk)
    if not ev.publico and not _interno(request):
        raise Http404
    return render(request, "calendario/evento_detail.html", {"ev": ev, "interno": _interno(request)})


def calendario_ics(request):
    eventos = Evento.objects.filter(publico=True).order_by("data_inicio")
    conteudo = gerar_ics(eventos, f"Calendário — {configuracao.escola()['nome']}", dominio=request.get_host())
    resp = HttpResponse(conteudo, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'inline; filename="calendario-escolar.ics"'
    return resp


def _ctx_impressao(request, ano, pdf=False):
    ctx = _montar_ano(ano, interno=False)
    ano_letivo = AnoLetivo.objects.filter(ano=ano).first()
    ctx.update({"ano": ano, "esc": doc_servicos.dados_escola(), "resumo": servicos.dias_letivos(ano_letivo) if ano_letivo else None})
    if pdf:
        ctx.update(doc_servicos.contexto_pdf(extras=("css/calendario.css",)))
    else:
        ctx.update({"pdf": False, "logo_src": static("img/logo-doc.png"), "pdf_disponivel": doc_servicos.pdf_disponivel() and _interno(request)})
    return ctx


def calendario_imprimir(request, ano):
    _ano_valido(ano)
    return render(request, "calendario/imprimir.html", _ctx_impressao(request, ano))


@staff_required
def calendario_pdf(request, ano):
    _ano_valido(ano)
    if not doc_servicos.pdf_disponivel():
        messages.error(request, "O download direto de PDF não está instalado. Use Imprimir → Salvar como PDF.")
        return redirect("calendario_imprimir", ano=ano)
    pdf = doc_servicos.renderizar_pdf("calendario/imprimir.html", _ctx_impressao(request, ano, pdf=True), request)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="calendario-escolar-{ano}.pdf"'
    return resp


# ---------- gestão (equipe) ----------
@staff_required
def evento_list(request):
    qs = Evento.objects.prefetch_related("turmas")
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("categoria", "")
    ano = request.GET.get("ano", str(date.today().year))
    if q:
        qs = qs.filter(titulo__icontains=q)
    if cat in Categoria.values:
        qs = qs.filter(categoria=cat)
    if ano.isdigit():
        qs = qs.filter(data_inicio__year=int(ano))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "calendario/evento_lista.html", {
        "page_obj": Paginator(qs, 30).get_page(request.GET.get("page")),
        "categorias": Categoria.choices, "f": {"q": q, "categoria": cat, "ano": ano}, "qs": params.urlencode(),
    })


@staff_required
def evento_form(request, pk=None):
    ev = get_object_or_404(Evento, pk=pk) if pk else None
    if request.method == "POST":
        form = EventoForm(request.POST, instance=ev)
        if form.is_valid():
            ev = form.save()
            messages.success(request, "Evento salvo.")
            return redirect("evento_detail", pk=ev.pk)
    else:
        initial = None
        if not ev:
            initial = {"publico": True}
            try:
                initial["data_inicio"] = date.fromisoformat(request.GET.get("data", ""))
            except ValueError:
                pass
        form = EventoForm(instance=ev, initial=initial)
    return render(request, "calendario/evento_form.html", {
        "form": form, "ev": ev, "padroes": {c: c in SEM_AULA_PADRAO for c in Categoria.values},
    })


@staff_required
@require_POST
def evento_excluir(request, pk):
    ev = get_object_or_404(Evento, pk=pk)
    ev.delete()
    messages.success(request, f"Evento \"{ev.titulo}\" excluído.")
    return redirect("evento_list")


@staff_required
def feriados_gerar(request):
    hoje = date.today()
    cfg = configuracao.calendario()
    entrada = request.POST if request.method == "POST" else request.GET
    ano = int(entrada["ano"]) if entrada.get("ano", "").isdigit() else hoje.year
    _ano_valido(ano)
    comemorativas = (entrada.get("comemorativas") == "on") if request.method == "POST" else True

    if request.method == "POST":
        criados, existentes = servicos.gerar_feriados(ano, cfg["uf"], cfg["municipio"], comemorativas)
        messages.success(request, f"Calendário de {ano}: {criados} evento(s) criado(s), {existentes} já existia(m).")
        return redirect(f"{request.path}?ano={ano}")

    ja = set(Evento.objects.filter(origem=Evento.Origem.AUTOMATICO, data_inicio__year=ano)
             .values_list("titulo", "data_inicio"))
    previa = [dict(i, existe=(i["titulo"], i["data"]) in ja)
              for i in feriados.gerar(ano, cfg["uf"], cfg["municipio"], comemorativas)]
    return render(request, "calendario/feriados.html", {
        "ano": ano, "anos": range(hoje.year - 1, hoje.year + 3), "previa": previa, "cfg": cfg,
        "tem_municipais": feriados.tem_municipais(cfg["uf"], cfg["municipio"]),
        "municipios": feriados.municipios_cadastrados(), "rotulos": ROTULOS,
        "novos": sum(1 for i in previa if not i["existe"]),
    })


@staff_required
def ano_configurar(request, pk):
    ano = get_object_or_404(AnoLetivo, pk=pk)
    data = request.POST or None
    form = AnoLetivoConfigForm(data, instance=ano)
    periodos = PeriodoFormSet(data, instance=ano, prefix="per")
    if request.method == "POST":
        if all([form.is_valid(), periodos.is_valid()]):
            with transaction.atomic():
                form.save()
                periodos.save()
            messages.success(request, f"Ano letivo {ano.ano} configurado.")
            return redirect(f"/calendario/dias-letivos/?ano={ano.pk}")
        messages.error(request, "Revise os campos destacados e tente de novo.")
    return render(request, "calendario/ano_configurar.html", {"ano": ano, "form": form, "periodos": periodos})


@staff_required
def dias_letivos_view(request):
    anos = AnoLetivo.objects.all()
    sel = anos.filter(pk=request.GET["ano"]).first() if request.GET.get("ano", "").isdigit() else AnoLetivo.padrao()
    resultado = servicos.dias_letivos(sel) if sel else None
    return render(request, "calendario/dias_letivos.html", {
        "anos": anos, "sel": sel, "r": resultado, "minimo_dias": servicos.DIAS_LETIVOS_MINIMO,
        "minimo_horas": servicos.HORAS_MINIMO, "nomes_mes": NOMES_MES,
    })
