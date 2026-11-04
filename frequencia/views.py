import calendar
import csv
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from alunos.models import Aluno
from calendario.models import PeriodoLetivo
from core.mixins import staff_required
from matriculas.models import AnoLetivo, Turma

from . import servicos
from .forms import BuscaAlunoForm
from .models import Chamada, Presenca

S = Presenca.Status


def _data(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise Http404("Data inválida.")


def _data_ou(texto, padrao):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return padrao


# ---------- escolher data e turma ----------
@staff_required
def inicio(request):
    hoje = date.today()
    dia = min(_data_ou(request.GET.get("data"), hoje), hoje)
    ano = AnoLetivo.padrao()
    turmas = Turma.objects.filter(ano_letivo=ano) if ano else Turma.objects.none()
    cartoes = []
    for t in turmas:
        ch = Chamada.objects.filter(turma=t, data=dia).first()
        cartoes.append({
            "turma": t, "chamada": ch,
            "alunos": servicos.matriculas_da_chamada(t, dia, ch).count(),
            "resumo": servicos.totais_chamada(ch) if ch else None,
        })
    letivo, motivo = (True, "")
    if turmas:
        letivo, motivo = servicos.situacao_do_dia(turmas[0], dia)
    return render(request, "frequencia/inicio.html", {
        "dia": dia, "hoje": hoje, "ontem": dia - timedelta(days=1),
        "amanha": dia + timedelta(days=1) if dia < hoje else None,
        "cartoes": cartoes, "ano": ano, "letivo": letivo, "motivo": motivo,
    })


# ---------- chamada do dia ----------
def _linhas_da_chamada(mats, existentes):
    return [{"m": m, "status": existentes[m.pk].status if m.pk in existentes else S.PRESENTE,
             "just": existentes[m.pk].justificativa if m.pk in existentes else "", "erro": ""} for m in mats]


@staff_required
def chamada(request, turma_pk, data):
    turma = get_object_or_404(Turma.objects.select_related("ano_letivo"), pk=turma_pk)
    dia = _data(data)
    hoje = date.today()
    if dia > hoje:
        messages.error(request, "Não é possível fazer a chamada de um dia que ainda não chegou.")
        return redirect(reverse("frequencia"))
    ch = Chamada.objects.filter(turma=turma, data=dia).first()
    mats = list(servicos.matriculas_da_chamada(turma, dia, ch))
    existentes = {p.matricula_id: p for p in ch.presencas.all()} if ch else {}
    linhas = _linhas_da_chamada(mats, existentes)
    observacao = ch.observacao if ch else ""

    if request.method == "POST":
        observacao = request.POST.get("observacao", "")
        gravar, tem_erro = {}, False
        for linha in linhas:
            pk = linha["m"].pk
            status, just = request.POST.get(f"status_{pk}", ""), request.POST.get(f"just_{pk}", "")
            linha["status"], linha["just"] = status, just
            if status not in S.values:
                linha["erro"], tem_erro = "Marque presença ou falta.", True
            elif status == S.JUSTIFICADA and not just.strip():
                linha["erro"], tem_erro = "Informe a justificativa da falta.", True
            else:
                gravar[pk] = (status, just)
        if not linhas:
            messages.error(request, "Esta turma não tem alunos ativos nesta data.")
        elif tem_erro:
            messages.error(request, "A chamada não foi salva. Veja os alunos marcados em vermelho.")
        else:
            servicos.salvar_chamada(turma, dia, request.user, gravar, observacao)
            faltas = sum(1 for s, _ in gravar.values() if s != S.PRESENTE)
            messages.success(request, f"Chamada de {turma.nome} salva: {len(gravar) - faltas} presentes e {faltas} falta(s).")
            return redirect(reverse("frequencia") + "?" + urlencode({"data": dia.isoformat()}))

    letivo, motivo = servicos.situacao_do_dia(turma, dia)
    return render(request, "frequencia/chamada.html", {
        "turma": turma, "dia": dia, "linhas": linhas, "chamada": ch, "observacao": observacao,
        "letivo": letivo, "motivo": motivo,
        "anterior": dia - timedelta(days=1), "seguinte": dia + timedelta(days=1) if dia < hoje else None,
    })


@staff_required
@require_POST
def chamada_excluir(request, turma_pk, data):
    turma = get_object_or_404(Turma, pk=turma_pk)
    dia = _data(data)
    apagadas, _ = Chamada.objects.filter(turma=turma, data=dia).delete()
    if apagadas:
        messages.success(request, f"Chamada de {turma.nome} em {dia:%d/%m/%Y} excluída (o dia deixa de contar como aula).")
    return redirect(reverse("frequencia") + "?" + urlencode({"data": dia.isoformat()}))


# ---------- consulta por aluno ----------
@staff_required
def consulta_aluno(request):
    form = BuscaAlunoForm(request.GET or None)
    if request.GET and form.is_valid():
        return redirect("frequencia_aluno", pk=form.cleaned_data["aluno"].pk)
    return render(request, "frequencia/consulta_aluno.html", {"form": form})


def _periodo_padrao_aluno(aluno):
    hoje = date.today()
    mat = aluno.matriculas.select_related("ano_letivo").order_by("-ano_letivo__ano").first()
    if not mat:
        return date(hoje.year, 1, 1), hoje
    ano = mat.ano_letivo
    ini = ano.inicio_aulas or date(ano.ano, 1, 1)
    fim = min(ano.fim_aulas or date(ano.ano, 12, 31), hoje)
    return ini, max(fim, ini)


@staff_required
def frequencia_do_aluno(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    ini_padrao, fim_padrao = _periodo_padrao_aluno(aluno)
    inicio = _data_ou(request.GET.get("inicio"), ini_padrao)
    fim = _data_ou(request.GET.get("fim"), fim_padrao)
    erro = ""
    if inicio > fim:
        erro, inicio, fim = "O início do período não pode ser depois do fim.", ini_padrao, fim_padrao
    blocos = servicos.frequencia_aluno(aluno, inicio, fim)
    for b in blocos:
        b["declaracao"] = reverse("documento_form", args=["declaracao-frequencia", aluno.pk]) + "?" + urlencode({
            "matricula": b["matricula"].pk, "periodo_inicio": inicio.isoformat(), "periodo_fim": fim.isoformat(),
            "da_frequencia": "1"})
    hoje = date.today()
    mes_ini = hoje.replace(day=1)
    return render(request, "frequencia/aluno.html", {
        "aluno": aluno, "inicio": inicio, "fim": fim, "blocos": blocos, "erro": erro,
        "atalhos": [("Ano letivo", ini_padrao, fim_padrao), ("Este mês", mes_ini, hoje)],
    })


# ---------- relatório da turma (mensal ou consolidado) ----------
def _mes(texto):
    try:
        ano, mes = texto.split("-")
        primeiro = date(int(ano), int(mes), 1)
    except (AttributeError, ValueError):
        return None
    return primeiro, primeiro.replace(day=calendar.monthrange(primeiro.year, primeiro.month)[1])


@staff_required
def relatorio(request):
    hoje = date.today()
    ano = AnoLetivo.padrao()
    turmas = list(Turma.objects.select_related("ano_letivo").order_by("-ano_letivo__ano", "nome", "turno"))
    turma = None
    if request.GET.get("turma", "").isdigit():
        turma = next((t for t in turmas if t.pk == int(request.GET["turma"])), None)
    if turma is None and turmas:
        turma = next((t for t in turmas if ano and t.ano_letivo_id == ano.pk), turmas[0])

    mes_txt = request.GET.get("mes", "")
    intervalo = _mes(mes_txt)
    if request.GET.get("inicio") or request.GET.get("fim"):
        inicio = _data_ou(request.GET.get("inicio"), hoje.replace(day=1))
        fim = _data_ou(request.GET.get("fim"), hoje)
        mes_txt = ""
    elif intervalo:
        inicio, fim = intervalo
    else:
        inicio, fim = _mes(f"{hoje.year}-{hoje.month}")
        mes_txt = f"{hoje.year}-{hoje.month:02d}"
    erro = ""
    if inicio > fim:
        erro, (inicio, fim) = "O início do período não pode ser depois do fim.", _mes(f"{hoje.year}-{hoje.month}")

    dados = servicos.relatorio_turma(turma, inicio, fim) if turma and not erro else None
    if dados is not None and request.GET.get("formato") == "csv":
        return _csv_relatorio(turma, inicio, fim, dados)

    atalhos = []
    if turma:
        a = turma.ano_letivo
        atalhos.append(("Ano letivo inteiro", a.inicio_aulas or date(a.ano, 1, 1), a.fim_aulas or date(a.ano, 12, 31)))
        atalhos += [(p.nome, p.inicio, p.fim) for p in PeriodoLetivo.objects.filter(ano_letivo=a)]
    return render(request, "frequencia/relatorio.html", {
        "turmas": turmas, "turma": turma, "inicio": inicio, "fim": fim, "mes": mes_txt, "erro": erro,
        "d": dados, "grade": bool(dados) and 0 < len(dados["dias"]) <= 31,
        "atalhos": atalhos, "hoje": hoje,
    })


def _csv_relatorio(turma, inicio, fim, d):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="frequencia-{turma.pk}-{inicio:%Y%m%d}-{fim:%Y%m%d}.csv"'
    resp.write("﻿")  # o Excel reconhece os acentos
    w = csv.writer(resp, delimiter=";")
    w.writerow([f"Frequência — {turma}", f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"])
    mostrar_dias = len(d["dias"]) <= 31
    w.writerow(["Aluno", "Dias com chamada", "Presenças", "Faltas", "Faltas justificadas", "Frequência (%)"]
               + ([f"{x:%d/%m}" for x in d["dias"]] if mostrar_dias else []))
    for l in d["linhas"]:
        pct = str(l["percentual"]).replace(".", ",") if l["percentual"] is not None else ""
        extra = [p.status if p else "" for p in l["grade"]] if mostrar_dias else []
        w.writerow([l["aluno"].nome, l["dias"], l["presencas"], l["faltas"], l["justificadas"], pct] + extra)
    return resp
