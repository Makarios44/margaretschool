"""Regras da frequência diária: quem entra na chamada, contagens, percentuais e dias sem chamada."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Q

from calendario.models import Categoria
from calendario.servicos import eventos_entre
from documentos import regras
from matriculas.models import Matricula

from .models import Chamada, Presenca

S = Presenca.Status


# ---------- quem entra na chamada ----------
def matriculas_da_chamada(turma, data, chamada=None):
    """Alunos ativos da turma na data (matriculados até aquele dia), mais quem já consta nesta chamada."""
    filtro = Q(situacao=Matricula.Situacao.ATIVO, data_matricula__lte=data)
    if chamada is not None and chamada.pk:
        filtro |= Q(presencas__chamada=chamada)
    return (Matricula.objects.filter(turma=turma).filter(filtro).distinct()
            .select_related("aluno").order_by("aluno__nome_busca", "aluno__nome"))


# ---------- dia letivo segundo o calendário ----------
def situacao_do_dia(turma, data):
    """(é_dia_letivo, motivo): usa o calendário; o professor pode registrar mesmo assim (ex.: reposição)."""
    eventos = eventos_entre(data, data, interno=True, turma_id=turma.pk)
    for ev in eventos:
        if ev.sem_aula and (not ev.turmas.all() or turma in ev.turmas.all()):
            return False, ev.titulo
    if data.weekday() >= 5 and not any(ev.categoria == Categoria.SABADO_LETIVO for ev in eventos):
        return False, "Fim de semana"
    ano = turma.ano_letivo
    if ano.inicio_aulas and data < ano.inicio_aulas:
        return False, "Antes do início das aulas"
    if ano.fim_aulas and data > ano.fim_aulas:
        return False, "Depois do fim das aulas"
    return True, ""


def dias_esperados(turma, inicio, fim):
    """Dias letivos pelo calendário entre as datas (usado para apontar chamadas que faltam)."""
    ano = turma.ano_letivo  # fora do ano letivo da turma não se espera chamada
    inicio = max(inicio, ano.inicio_aulas or date(ano.ano, 1, 1))
    fim = min(fim, ano.fim_aulas or date(ano.ano, 12, 31))
    if fim < inicio:
        return []
    sem_aula, extras = set(), set()
    for ev in eventos_entre(inicio, fim, interno=True, turma_id=turma.pk):
        for d in ev.dias():
            if ev.sem_aula:
                sem_aula.add(d)
            if ev.categoria == Categoria.SABADO_LETIVO:
                extras.add(d)
    dias, d = [], inicio
    while d <= fim:
        if d not in sem_aula and (d.weekday() < 5 or d in extras):
            dias.append(d)
        d += timedelta(days=1)
    return dias


def chamadas_pendentes(turma, inicio, fim):
    """Dias letivos (até hoje) sem chamada registrada."""
    fim = min(fim, date.today())
    feitos = set(Chamada.objects.filter(turma=turma, data__range=(inicio, fim)).values_list("data", flat=True))
    return [d for d in dias_esperados(turma, inicio, fim) if d not in feitos]


# ---------- gravação ----------
@transaction.atomic
def salvar_chamada(turma, data, usuario, linhas, observacao=""):
    """linhas: {matricula_id: (status, justificativa)}. Atualiza a chamada do dia ou cria uma nova."""
    chamada, _ = Chamada.objects.get_or_create(turma=turma, data=data, defaults={"registrada_por": usuario})
    chamada.observacao = observacao.strip()[:200]
    chamada.registrada_por = usuario
    chamada.save()
    for mat_id, (status, just) in linhas.items():
        Presenca.objects.update_or_create(
            chamada=chamada, matricula_id=mat_id,
            defaults={"status": status, "justificativa": just.strip()[:200] if status != S.PRESENTE else ""},
        )
    return chamada


# ---------- contagens ----------
def percentual(presencas, total):
    if not total:
        return None
    return (Decimal(presencas) / Decimal(total) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _contar(qs):
    """Totais de um conjunto de presenças. Falta justificada também é falta (conta na frequência)."""
    dados = {S.PRESENTE: 0, S.FALTA: 0, S.JUSTIFICADA: 0}
    for status in qs.values_list("status", flat=True):
        dados[status] += 1
    dias = sum(dados.values())
    faltas = dados[S.FALTA] + dados[S.JUSTIFICADA]
    return {
        "dias": dias, "presencas": dados[S.PRESENTE], "faltas": faltas,
        "justificadas": dados[S.JUSTIFICADA], "injustificadas": dados[S.FALTA],
        "percentual": percentual(dados[S.PRESENTE], dias),
    }


def resumo_matricula(matricula, inicio, fim):
    return _contar(Presenca.objects.filter(matricula=matricula, chamada__data__range=(inicio, fim)))


def frequencia_aluno(aluno, inicio, fim):
    """Frequência do aluno no período, por matrícula (ano letivo), com a lista de faltas."""
    blocos = []
    mats = (Matricula.objects.filter(aluno=aluno).select_related("turma", "ano_letivo")
            .order_by("ano_letivo__ano"))
    for m in mats:
        qs = Presenca.objects.filter(matricula=m, chamada__data__range=(inicio, fim))
        resumo = _contar(qs)
        if not resumo["dias"]:
            continue
        faltas = list(qs.exclude(status=S.PRESENTE).select_related("chamada").order_by("chamada__data"))
        minimo = regras.frequencia_minima(m.etapa)
        abaixo = bool(minimo and resumo["percentual"] is not None and resumo["percentual"] < minimo)
        blocos.append({"matricula": m, "resumo": resumo, "faltas": faltas, "minimo": minimo, "abaixo": abaixo,
                       "base_minimo": regras.BASE_FREQUENCIA.get(m.etapa, "")})
    return blocos


def relatorio_turma(turma, inicio, fim):
    """Linhas por aluno + grade dia a dia + dias sem chamada, para o relatório mensal/consolidado."""
    chamadas = list(Chamada.objects.filter(turma=turma, data__range=(inicio, fim)).order_by("data"))
    dias = [c.data for c in chamadas]
    por_mat = defaultdict(dict)
    for p in Presenca.objects.filter(chamada__in=chamadas).select_related("chamada"):
        por_mat[p.matricula_id][p.chamada.data] = p
    ids_com_registro = set(por_mat)
    mats = (Matricula.objects.filter(turma=turma)
            .filter(Q(situacao=Matricula.Situacao.ATIVO, data_matricula__lte=fim) | Q(pk__in=ids_com_registro))
            .select_related("aluno").order_by("aluno__nome_busca", "aluno__nome"))
    minimo = regras.frequencia_minima(turma.etapa)
    linhas = []
    for m in mats:
        registros = por_mat.get(m.pk, {})
        cont = {S.PRESENTE: 0, S.FALTA: 0, S.JUSTIFICADA: 0}
        for p in registros.values():
            cont[p.status] += 1
        total = sum(cont.values())
        pct = percentual(cont[S.PRESENTE], total)
        linhas.append({
            "matricula": m, "aluno": m.aluno, "dias": total, "presencas": cont[S.PRESENTE],
            "faltas": cont[S.FALTA] + cont[S.JUSTIFICADA], "justificadas": cont[S.JUSTIFICADA],
            "percentual": pct, "abaixo": bool(minimo and pct is not None and pct < minimo),
            "grade": [registros.get(d) for d in dias],
            "inativo": m.situacao != Matricula.Situacao.ATIVO,
        })
    total_presencas = sum(l["presencas"] for l in linhas)
    total_registros = sum(l["dias"] for l in linhas)
    return {
        "linhas": linhas, "dias": dias, "chamadas": chamadas, "minimo": minimo,
        "base_minimo": regras.BASE_FREQUENCIA.get(turma.etapa, ""),
        "dias_com_chamada": len(dias), "pendentes": chamadas_pendentes(turma, inicio, fim),
        "percentual_turma": percentual(total_presencas, total_registros),
        "total_faltas": sum(l["faltas"] for l in linhas),
    }


def totais_chamada(chamada):
    return _contar(chamada.presencas.all())
