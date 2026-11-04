import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from alunos.utils import filtrar_por_nome
from core.mixins import staff_required
from matriculas.models import Matricula

from .forms import CobrancaForm, DespesaForm, GerarMensalidadesForm, PagamentoForm
from .models import LIQUIDO, CategoriaDespesa, Cobranca, Despesa

C = Cobranca  # atalho


def _primeiro_dia(d):
    return d.replace(day=1)


def _ultimo_dia(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1) - timedelta(days=1)


def _parse_mes(raw):
    """'2026-10' -> date(2026, 10, 1); inválido -> mês atual."""
    try:
        ano, mes = raw.strip().split("-")
        return date(int(ano), int(mes), 1)
    except (ValueError, AttributeError):
        return _primeiro_dia(date.today())


def _soma(valor):
    return valor or Decimal("0.00")


@staff_required
def cobranca_list(request):
    hoje = date.today()
    qs = C.objects.select_related("matricula__aluno", "matricula__turma", "matricula__ano_letivo")

    if "mes" in request.GET:  # "" = todos os meses
        mes = _parse_mes(request.GET["mes"]) if request.GET["mes"].strip() else None
    else:
        mes = _primeiro_dia(hoje)
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    tipo = request.GET.get("tipo", "")

    if mes:
        qs = qs.filter(vencimento__range=(mes, _ultimo_dia(mes)))
    if q:
        qs = filtrar_por_nome(qs, q, "matricula__aluno__nome_busca")
    if tipo in C.Tipo.values:
        qs = qs.filter(tipo=tipo)
    if status == "pendente":
        qs = qs.filter(situacao=C.Situacao.ABERTA, vencimento__gte=hoje)
    elif status == "vencida":
        qs = qs.filter(situacao=C.Situacao.ABERTA, vencimento__lt=hoje)
    elif status == "paga":
        qs = qs.filter(situacao=C.Situacao.PAGA)
    elif status == "cancelada":
        qs = qs.filter(situacao=C.Situacao.CANCELADA)
    else:
        qs = qs.exclude(situacao=C.Situacao.CANCELADA)

    resumo = qs.exclude(situacao=C.Situacao.CANCELADA).aggregate(
        previsto=Sum(LIQUIDO),
        recebido=Sum("valor_pago", filter=Q(situacao=C.Situacao.PAGA)),
        aberto=Sum(LIQUIDO, filter=Q(situacao=C.Situacao.ABERTA)),
        vencido=Sum(LIQUIDO, filter=Q(situacao=C.Situacao.ABERTA, vencimento__lt=hoje)),
    )
    resumo = {k: _soma(v) for k, v in resumo.items()}

    qs = qs.order_by("vencimento", "matricula__aluno__nome", "id")
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "financeiro/cobranca_list.html", {
        "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")),
        "resumo": resumo,
        "f": {"mes": mes.strftime("%Y-%m") if mes else "", "q": q, "status": status, "tipo": tipo},
        "tipos": C.Tipo.choices,
        "qs": params.urlencode(),
    })


@staff_required
def cobranca_detail(request, pk):
    c = get_object_or_404(C.objects.select_related("matricula__aluno", "matricula__turma", "matricula__ano_letivo"), pk=pk)
    multa = juros = None
    if c.aberta and c.dias_atraso():
        multa, juros = c.calcular_encargos()
    return render(request, "financeiro/cobranca_detail.html", {
        "c": c, "multa_hoje": multa, "juros_hoje": juros,
    })


@staff_required
def cobranca_form(request, pk=None):
    c = get_object_or_404(C, pk=pk) if pk else None
    if c and not c.aberta:
        messages.error(request, "Só cobranças em aberto podem ser editadas. Estorne o pagamento primeiro, se necessário.")
        return redirect("cobranca_detail", pk=c.pk)
    if request.method == "POST":
        form = CobrancaForm(request.POST, instance=c)
        if form.is_valid():
            c = form.save()
            messages.success(request, "Cobrança salva.")
            return redirect("cobranca_detail", pk=c.pk)
    else:
        initial = None
        if not c:
            initial = {"tipo": C.Tipo.AVULSA, "vencimento": date.today()}
            if request.GET.get("matricula", "").isdigit():
                initial["matricula"] = int(request.GET["matricula"])
        form = CobrancaForm(instance=c, initial=initial)
    return render(request, "financeiro/cobranca_form.html", {"form": form, "c": c})


@staff_required
def cobranca_receber(request, pk):
    c = get_object_or_404(C.objects.select_related("matricula__aluno"), pk=pk)
    if not c.aberta:
        messages.error(request, "Esta cobrança não está em aberto.")
        return redirect("cobranca_detail", pk=c.pk)

    if request.method == "POST":
        form = PagamentoForm(request.POST, cobranca=c)
        if form.is_valid():
            d = form.cleaned_data
            c.registrar_pagamento(
                d["data_pagamento"], d["forma_pagamento"], desconto=d["desconto"],
                multa=d["multa"], juros=d["juros"], observacoes=d["observacoes"],
            )
            messages.success(request, "Pagamento registrado. O recibo já está disponível.")
            return redirect("cobranca_detail", pk=c.pk)
    else:
        hoje = date.today()
        multa, juros = c.calcular_encargos(hoje)
        form = PagamentoForm(cobranca=c, initial={
            "data_pagamento": hoje, "desconto": c.desconto, "multa": multa, "juros": juros,
            "observacoes": c.observacoes,
        })
    return render(request, "financeiro/cobranca_receber.html", {"form": form, "c": c})


@staff_required
@require_POST
def cobranca_cancelar(request, pk):
    c = get_object_or_404(C, pk=pk)
    if c.aberta:
        c.cancelar()
        messages.success(request, "Cobrança cancelada.")
    else:
        messages.error(request, "Só cobranças em aberto podem ser canceladas.")
    return redirect("cobranca_detail", pk=pk)


@staff_required
@require_POST
def cobranca_estornar(request, pk):
    c = get_object_or_404(C, pk=pk)
    if c.paga:
        c.estornar()
        messages.success(request, "Pagamento estornado. A cobrança voltou para em aberto.")
    else:
        messages.error(request, "Só cobranças pagas podem ser estornadas.")
    return redirect("cobranca_detail", pk=pk)


@staff_required
def cobranca_recibo(request, pk):
    c = get_object_or_404(C.objects.select_related("matricula__aluno", "matricula__turma", "matricula__ano_letivo")
                          .prefetch_related("matricula__aluno__responsaveis"), pk=pk)
    if not c.paga:
        messages.error(request, "O recibo só existe depois que o pagamento é registrado.")
        return redirect("cobranca_detail", pk=c.pk)
    return render(request, "financeiro/recibo.html", {
        "c": c, "m": c.matricula, "pagador": c.matricula.aluno.contratante,
    })


@staff_required
def gerar_mensalidades(request, matricula_pk):
    m = get_object_or_404(Matricula.objects.select_related("aluno", "ano_letivo"), pk=matricula_pk)
    if m.situacao != Matricula.Situacao.ATIVO:
        messages.error(request, "Só é possível gerar mensalidades para matrículas ativas.")
        return redirect("matricula_detail", pk=m.pk)

    ano = m.ano_letivo.ano
    vigentes = m.cobrancas.exclude(situacao=C.Situacao.CANCELADA)
    tem_taxa = vigentes.filter(tipo=C.Tipo.TAXA_MATRICULA).exists()
    oferecer_taxa = m.taxa_matricula > 0 and not m.taxa_paga and not tem_taxa

    if request.method == "POST":
        form = GerarMensalidadesForm(request.POST, mostrar_taxa=oferecer_taxa)
        if form.is_valid():
            d = form.cleaned_data
            criadas = puladas = 0
            with transaction.atomic():
                for i in range(d["quantidade"]):
                    mes = d["mes_inicial"] + i
                    competencia = date(ano, mes, 1)
                    if vigentes.filter(tipo=C.Tipo.MENSALIDADE, competencia=competencia).exists():
                        puladas += 1
                        continue
                    C.objects.create(
                        matricula=m, tipo=C.Tipo.MENSALIDADE,
                        descricao=f"Mensalidade {mes:02d}/{ano}",
                        competencia=competencia, vencimento=date(ano, mes, m.dia_vencimento),
                        valor=m.mensalidade, desconto=m.desconto_valor,
                        motivo_desconto=m.desconto_descricao if m.desconto_valor else "",
                    )
                    criadas += 1
                if d.get("incluir_taxa"):
                    # se a matrícula é antiga, vence hoje (evita nascer já com multa)
                    C.objects.create(
                        matricula=m, tipo=C.Tipo.TAXA_MATRICULA,
                        descricao=f"Taxa de matrícula {ano}",
                        vencimento=max(m.data_matricula, date.today()), valor=m.taxa_matricula,
                    )
            texto = f"{criadas} mensalidade{'s' if criadas != 1 else ''} gerada{'s' if criadas != 1 else ''}."
            if puladas:
                texto += f" {puladas} já existia{'m' if puladas != 1 else ''} e foi mantida{'s' if puladas != 1 else ''}."
            if d.get("incluir_taxa"):
                texto += " Taxa de matrícula incluída."
            messages.success(request, texto)
            return redirect("matricula_detail", pk=m.pk)
    else:
        ultima = vigentes.filter(tipo=C.Tipo.MENSALIDADE).order_by("-competencia").first()
        if ultima:
            inicial = min(ultima.competencia.month + 1, 12)
        elif m.data_matricula.year == ano:
            inicial = m.data_matricula.month
        else:
            inicial = 1
        form = GerarMensalidadesForm(
            mostrar_taxa=oferecer_taxa,
            initial={"mes_inicial": inicial, "quantidade": 13 - inicial, "incluir_taxa": oferecer_taxa},
        )
    return render(request, "financeiro/gerar.html", {"form": form, "m": m, "ano": ano})


@staff_required
def relatorio_mensal(request):
    hoje = date.today()
    mes = _parse_mes(request.GET["mes"]) if request.GET.get("mes") else _primeiro_dia(hoje)
    fim = _ultimo_dia(mes)
    anterior, proximo = _primeiro_dia(mes - timedelta(days=1)), fim + timedelta(days=1)

    # 1) Caixa: o que foi efetivamente recebido no mês
    pagos = C.objects.filter(situacao=C.Situacao.PAGA, data_pagamento__range=(mes, fim))
    caixa = pagos.aggregate(
        total=Sum("valor_pago"), multas=Sum("multa"), juros=Sum("juros"), n=Count("id"),
    )
    caixa = {k: (_soma(v) if k != "n" else v) for k, v in caixa.items()}
    formas = dict(C.Forma.choices)
    por_forma = [
        {"nome": formas.get(r["forma_pagamento"], r["forma_pagamento"]), "total": r["total"], "n": r["n"]}
        for r in pagos.values("forma_pagamento").annotate(total=Sum("valor_pago"), n=Count("id")).order_by("-total")
    ]
    tipos = dict(C.Tipo.choices)
    por_tipo = [
        {"nome": tipos.get(r["tipo"], r["tipo"]), "total": r["total"], "n": r["n"]}
        for r in pagos.values("tipo").annotate(total=Sum("valor_pago"), n=Count("id")).order_by("-total")
    ]

    # 2) Cobranças que vencem no mês e inadimplência (posição de hoje)
    vencem = C.objects.filter(vencimento__range=(mes, fim)).exclude(situacao=C.Situacao.CANCELADA)
    atrasadas = Q(situacao=C.Situacao.ABERTA, vencimento__lt=hoje)
    comp = vencem.aggregate(
        n=Count("id"),
        previsto=Sum(LIQUIDO),
        pago=Sum(LIQUIDO, filter=Q(situacao=C.Situacao.PAGA)),
        aberto=Sum(LIQUIDO, filter=Q(situacao=C.Situacao.ABERTA)),
        vencido=Sum(LIQUIDO, filter=atrasadas),
        n_vencidas=Count("id", filter=atrasadas),
        descontos=Sum("desconto"),
    )
    comp = {k: (_soma(v) if k not in ("n", "n_vencidas") else v) for k, v in comp.items()}
    comp["inadimplencia_pct"] = (
        (comp["vencido"] / comp["previsto"] * 100).quantize(Decimal("0.1")) if comp["previsto"] else Decimal("0.0")
    )
    inadimplentes = (
        vencem.filter(atrasadas)
        .select_related("matricula__aluno", "matricula__turma")
        .prefetch_related("matricula__aluno__responsaveis")
        .order_by("vencimento", "matricula__aluno__nome")
    )
    comp["n_alunos"] = vencem.filter(atrasadas).values("matricula__aluno").distinct().count()
    acumulada = C.objects.filter(atrasadas).aggregate(total=Sum(LIQUIDO), n=Count("id"))

    despesas_mes = _soma(Despesa.objects.filter(data__range=(mes, fim)).aggregate(t=Sum("valor"))["t"])
    return render(request, "financeiro/relatorio.html", {
        "despesas_mes": despesas_mes, "resultado_mes": caixa["total"] - despesas_mes,
        "mes": mes, "anterior": anterior, "proximo": proximo,
        "caixa": caixa, "por_forma": por_forma, "por_tipo": por_tipo,
        "comp": comp, "inadimplentes": inadimplentes,
        "acumulada": {"total": _soma(acumulada["total"]), "n": acumulada["n"]},
    })


# ===================== DESPESAS E PAINEL FINANCEIRO =====================
MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
PALETA = ["#007CFC", "#01C058", "#F08C00", "#B83280", "#7B5CD6", "#138A8A", "#D64545", "#C9A800", "#6AA121"]
COR_OUTRAS = "#868E96"
ZERO = Decimal("0.00")


def _ano_param(request, padrao):
    ano = request.GET.get("ano", "")
    return int(ano) if ano.isdigit() and 1990 <= int(ano) <= 2100 else padrao


def _por_categoria(despesas, maximo=9):
    """Soma por categoria, com as menores agrupadas em 'Outras' e o gradiente do gráfico de pizza."""
    linhas = list(despesas.values("categoria__nome").annotate(total=Sum("valor")).order_by("-total"))
    total = sum((l["total"] for l in linhas), ZERO)
    itens = [{"nome": l["categoria__nome"], "total": l["total"]} for l in linhas]
    if len(itens) > maximo:
        resto = sum((i["total"] for i in itens[maximo - 1:]), ZERO)
        itens = itens[:maximo - 1] + [{"nome": "Outras categorias", "total": resto}]
    acumulado, partes = 0.0, []
    for i, item in enumerate(itens):
        item["cor"] = COR_OUTRAS if item["nome"] == "Outras categorias" else PALETA[i % len(PALETA)]
        item["pct"] = (item["total"] / total * 100) if total else Decimal(0)
        inicio, acumulado = acumulado, acumulado + float(item["pct"])
        partes.append(f"{item['cor']} {inicio:.2f}% {acumulado:.2f}%")
    return itens, total, ", ".join(partes)


@staff_required
def financeiro_painel(request):
    hoje = date.today()
    ano = _ano_param(request, hoje.year)
    mes = int(request.GET["mes"]) if request.GET.get("mes", "").isdigit() and 1 <= int(request.GET["mes"]) <= 12 else None

    recebido_mes = {r["m"]: r["t"] for r in Cobranca.objects.filter(
        situacao=Cobranca.Situacao.PAGA, data_pagamento__year=ano)
        .annotate(m=ExtractMonth("data_pagamento")).values("m").annotate(t=Sum("valor_pago")).order_by()}
    gasto_mes = {r["m"]: r["t"] for r in Despesa.objects.filter(data__year=ano)
                 .annotate(m=ExtractMonth("data")).values("m").annotate(t=Sum("valor")).order_by()}
    maximo = max([*recebido_mes.values(), *gasto_mes.values(), Decimal("0.01")])
    meses = []
    for n in range(1, 13):
        rec, gas = recebido_mes.get(n, ZERO), gasto_mes.get(n, ZERO)
        meses.append({
            "n": n, "nome": MESES_CURTOS[n - 1], "receitas": rec, "despesas": gas, "saldo": rec - gas,
            "pct_rec": max(float(rec / maximo * 100), 1.5) if rec else 0,
            "pct_gas": max(float(gas / maximo * 100), 1.5) if gas else 0,
            "selecionado": n == mes,
        })

    despesas = Despesa.objects.filter(data__year=ano)
    pagas = Cobranca.objects.filter(situacao=Cobranca.Situacao.PAGA, data_pagamento__year=ano)
    if mes:
        despesas, pagas = despesas.filter(data__month=mes), pagas.filter(data_pagamento__month=mes)
    receitas_periodo = _soma(pagas.aggregate(t=Sum("valor_pago"))["t"])
    categorias, despesas_periodo, gradiente = _por_categoria(despesas)

    anos = {hoje.year, ano}
    for campo, modelo in (("data", Despesa), ("data_pagamento", Cobranca)):
        for d in modelo.objects.exclude(**{f"{campo}__isnull": True}).dates(campo, "year"):
            anos.add(d.year)
    vencido = _soma(Cobranca.objects.filter(situacao=Cobranca.Situacao.ABERTA, vencimento__lt=hoje)
                    .aggregate(t=Sum(LIQUIDO))["t"])
    return render(request, "financeiro/painel.html", {
        "ano": ano, "mes": mes, "anos": sorted(anos, reverse=True),
        "meses_nomes": list(enumerate(MESES_CURTOS, 1)), "meses": meses,
        "receitas": receitas_periodo, "despesas_total": despesas_periodo,
        "resultado": receitas_periodo - despesas_periodo, "n_despesas": despesas.count(),
        "categorias": categorias, "gradiente": gradiente, "vencido": vencido,
        "maiores": despesas.select_related("categoria").order_by("-valor")[:5],
        "recentes": Despesa.objects.select_related("categoria")[:8],
        "periodo": f"{MESES_CURTOS[mes - 1]}/{ano}" if mes else str(ano),
    })


@staff_required
def despesa_list(request):
    qs = Despesa.objects.select_related("categoria")
    if "mes" in request.GET:  # "" = todos os meses
        mes = _parse_mes(request.GET["mes"]) if request.GET["mes"].strip() else None
    else:
        mes = _primeiro_dia(date.today())
    q = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "")
    forma = request.GET.get("forma", "")
    if mes:
        qs = qs.filter(data__range=(mes, _ultimo_dia(mes)))
    if q:
        qs = qs.filter(Q(descricao__icontains=q) | Q(fornecedor__icontains=q) | Q(numero_documento__icontains=q))
    if categoria.isdigit():
        qs = qs.filter(categoria_id=int(categoria))
    if forma in Despesa.Forma.values:
        qs = qs.filter(forma_pagamento=forma)
    resumo = qs.aggregate(total=Sum("valor"), n=Count("id"))

    if request.GET.get("formato") == "csv":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="despesas.csv"'
        resp.write("\ufeff")  # o Excel abre com acentos corretos
        escritor = csv.writer(resp, delimiter=";")
        escritor.writerow(["Data", "Descrição", "Categoria", "Fornecedor", "Forma de pagamento", "Nº documento", "Valor (R$)"])
        for d in qs:
            escritor.writerow([d.data.strftime("%d/%m/%Y"), d.descricao, d.categoria.nome, d.fornecedor,
                               d.get_forma_pagamento_display(), d.numero_documento, f"{d.valor:.2f}".replace(".", ",")])
        return resp

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "financeiro/despesa_list.html", {
        "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")),
        "total": _soma(resumo["total"]), "quantidade": resumo["n"],
        "categorias": CategoriaDespesa.objects.all(), "formas": Despesa.Forma.choices,
        "f": {"mes": mes.strftime("%Y-%m") if mes else "", "q": q, "categoria": categoria, "forma": forma},
        "qs": params.urlencode(),
    })


@staff_required
def despesa_form(request, pk=None):
    despesa = get_object_or_404(Despesa, pk=pk) if pk else None
    if request.method == "POST":
        form = DespesaForm(request.POST, request.FILES, instance=despesa)
        if form.is_valid():
            novo = despesa is None
            despesa = form.save(commit=False)
            if novo:
                despesa.criado_por = request.user
            despesa.save()
            messages.success(request, "Despesa lançada." if novo else "Despesa atualizada.")
            if novo and request.POST.get("acao") == "salvar_e_novo":
                return redirect("despesa_create")
            return redirect("despesa_detail", pk=despesa.pk)
    else:
        form = DespesaForm(instance=despesa, initial=None if despesa else {"data": date.today()})
    return render(request, "financeiro/despesa_form.html", {"form": form, "despesa": despesa})


@staff_required
def despesa_detail(request, pk):
    despesa = get_object_or_404(Despesa.objects.select_related("categoria", "criado_por"), pk=pk)
    return render(request, "financeiro/despesa_detail.html", {"d": despesa})


@staff_required
@require_POST
def despesa_excluir(request, pk):
    despesa = get_object_or_404(Despesa, pk=pk)
    descricao = despesa.descricao
    despesa.delete()
    messages.success(request, f"Despesa \"{descricao}\" excluída.")
    return redirect("despesa_list")
