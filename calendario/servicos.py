import calendar
from collections import Counter, defaultdict
from datetime import date, time, timedelta
from decimal import Decimal

from django.db.models import Q

from alunos.models import Aluno
from matriculas.models import AnoLetivo

from . import feriados
from .models import PRIORIDADE, Categoria, Evento, PeriodoLetivo

DIAS_LETIVOS_MINIMO = 200
HORAS_MINIMO = 800


# ---------- consultas ----------
def sobrepoe(qs, inicio, fim):
    """Eventos que tocam o intervalo [inicio, fim]."""
    return qs.filter(data_inicio__lte=fim).filter(
        Q(data_fim__gte=inicio) | Q(data_fim__isnull=True, data_inicio__gte=inicio)
    )


def eventos_entre(inicio, fim, interno=False, categorias=None, turma_id=None):
    qs = Evento.objects.prefetch_related("turmas")
    if not interno:
        qs = qs.filter(publico=True)
    if categorias:
        qs = qs.filter(categoria__in=categorias)
    if turma_id:  # eventos da turma ou de toda a escola
        qs = qs.filter(Q(turmas__id=turma_id) | Q(turmas__isnull=True)).distinct()
    return list(sobrepoe(qs, inicio, fim))


class Aniversario:
    """Item virtual (não é gravado): aniversário de aluno ativo."""
    pk = None
    categoria = "aniversario"
    publico = False
    sem_aula = False
    hora_inicio = None

    def __init__(self, aluno, data):
        self.titulo = f"Aniversário: {aluno.nome.split()[0]} ({data.year - aluno.data_nascimento.year} anos)"
        self.data_inicio = data

    def get_categoria_display(self):
        return "Aniversário de aluno"


def aniversarios(ano, mes):
    alunos = Aluno.objects.filter(data_nascimento__month=mes, matriculas__situacao="ativo").distinct()
    itens = []
    for a in alunos:
        dia = a.data_nascimento.day
        if mes == 2 and dia == 29 and not calendar.isleap(ano):
            dia = 28
        itens.append(Aniversario(a, date(ano, mes, dia)))
    return itens


def _ordem(ev):
    return (PRIORIDADE.get(ev.categoria, 99), ev.hora_inicio or time(0), ev.titulo)


def montar_mes(ano, mes, interno=False, categorias=None, turma_id=None, mostrar_aniversarios=False):
    """Semanas (domingo a sábado) com os eventos de cada dia."""
    semanas_datas = calendar.Calendar(firstweekday=6).monthdatescalendar(ano, mes)
    primeiro, ultimo = semanas_datas[0][0], semanas_datas[-1][-1]
    por_dia = defaultdict(list)
    for ev in eventos_entre(primeiro, ultimo, interno, categorias, turma_id):
        for d in ev.dias():
            if primeiro <= d <= ultimo:
                por_dia[d].append(ev)
    if mostrar_aniversarios:
        for ev in aniversarios(ano, mes):
            por_dia[ev.data_inicio].append(ev)
    hoje = date.today()
    semanas = []
    for sem in semanas_datas:
        dias = []
        for d in sem:
            evs = sorted(por_dia.get(d, []), key=_ordem)
            dias.append({
                "data": d, "no_mes": d.month == mes, "hoje": d == hoje, "fds": d.weekday() >= 5,
                "eventos": evs, "sem_aula": any(getattr(e, "sem_aula", False) for e in evs),
            })
        semanas.append(dias)
    return semanas


def categorias_presentes(semanas):
    vistas = {}
    for sem in semanas:
        for dia in sem:
            if dia["no_mes"]:
                for ev in dia["eventos"]:
                    vistas[ev.categoria] = ev
    return vistas


def proximos_eventos(limite=6, interno=False, a_partir_de=None):
    inicio = a_partir_de or date.today()
    qs = Evento.objects.exclude(categoria=Categoria.COMEMORATIVA).filter(
        Q(data_inicio__gte=inicio) | Q(data_fim__gte=inicio)
    )
    if not interno:
        qs = qs.filter(publico=True)
    return list(qs.order_by("data_inicio", "hora_inicio")[:limite])


# ---------- geração de feriados ----------
def _mesmo_dia_em(d, ano):
    try:
        return d.replace(year=ano)
    except ValueError:  # 29/02 em ano não bissexto
        return d.replace(year=ano, day=28)


def gerar_feriados(ano, uf, municipio, incluir_comemorativas=True):
    """Cria os eventos que ainda não existem. Retorna (criados, ja_existiam)."""
    criados = existentes = 0
    for item in feriados.gerar(ano, uf, municipio, incluir_comemorativas):
        _, novo = Evento.objects.get_or_create(
            titulo=item["titulo"], data_inicio=item["data"], categoria=item["categoria"],
            origem=Evento.Origem.AUTOMATICO,
            defaults={"sem_aula": item["sem_aula"], "descricao": item["descricao"], "publico": True,
                      "repete_anualmente": False},
        )
        criados += novo
        existentes += not novo
    # eventos marcados como "repete todo ano" em outros anos
    for modelo in Evento.objects.filter(repete_anualmente=True).exclude(data_inicio__year=ano):
        inicio = _mesmo_dia_em(modelo.data_inicio, ano)
        if Evento.objects.filter(titulo=modelo.titulo, categoria=modelo.categoria, data_inicio=inicio).exists():
            existentes += 1
            continue
        duracao = modelo.ultimo_dia - modelo.data_inicio
        copia = Evento.objects.create(
            titulo=modelo.titulo, categoria=modelo.categoria, data_inicio=inicio,
            data_fim=inicio + duracao if modelo.data_fim else None,
            hora_inicio=modelo.hora_inicio, hora_fim=modelo.hora_fim, local=modelo.local,
            descricao=modelo.descricao, sem_aula=modelo.sem_aula, publico=modelo.publico,
        )
        copia.turmas.set(modelo.turmas.all())
        criados += 1
    return criados, existentes


# ---------- dias letivos ----------
def dias_letivos(ano_letivo):
    """Conta os dias de efetivo trabalho escolar do ano letivo.

    Regra: dia letivo = dia útil (seg–sex) entre o início e o fim das aulas que não tenha evento
    "não há aula" para toda a escola, mais os sábados/domingos marcados como "Sábado letivo".
    Eventos só de algumas turmas não entram na conta geral.
    """
    ini, fim = ano_letivo.inicio_aulas, ano_letivo.fim_aulas
    if not (ini and fim) or fim < ini:
        return None
    sem_aula, extras = set(), set()
    for ev in sobrepoe(Evento.objects.prefetch_related("turmas"), ini, fim):
        if ev.turmas.all():
            continue
        for d in ev.dias():
            if ini <= d <= fim:
                if ev.sem_aula:
                    sem_aula.add(d)
                if ev.categoria == Categoria.SABADO_LETIVO:
                    extras.add(d)
    letivos, dias_sem_aula = [], []
    d = ini
    while d <= fim:
        util = d.weekday() < 5
        if d in sem_aula:
            if util:
                dias_sem_aula.append(d)
        elif util or d in extras:
            letivos.append(d)
        d += timedelta(days=1)

    por_mes = Counter((d.year, d.month) for d in letivos)
    meses, y, m = [], ini.year, ini.month
    while (y, m) <= (fim.year, fim.month):
        meses.append({"ano": y, "mes": m, "dias": por_mes.get((y, m), 0)})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    conjunto = set(letivos)
    periodos = [
        {"periodo": p, "dias": sum(1 for d in conjunto if p.inicio <= d <= p.fim)}
        for p in PeriodoLetivo.objects.filter(ano_letivo=ano_letivo)
    ]
    total = len(letivos)
    horas = Decimal(total) * ano_letivo.horas_dia_letivo
    return {
        "inicio": ini, "fim": fim, "total": total, "horas": horas,
        "por_mes": meses, "periodos": periodos, "dias_sem_aula": dias_sem_aula,
        "sabados_letivos": sorted(d for d in extras if d in conjunto),
        "faltam_dias": max(DIAS_LETIVOS_MINIMO - total, 0),
        "faltam_horas": max(Decimal(HORAS_MINIMO) - horas, Decimal(0)),
        "atende_dias": total >= DIAS_LETIVOS_MINIMO,
        "atende_horas": horas >= HORAS_MINIMO,
    }


def contagem_mensal(ano_letivo):
    """Dict {(ano, mes): dias letivos} para mostrar no cabeçalho do mês (ou {} se não configurado)."""
    r = dias_letivos(ano_letivo) if ano_letivo else None
    return {(m["ano"], m["mes"]): m["dias"] for m in r["por_mes"]} if r else {}
