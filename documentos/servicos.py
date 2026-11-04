"""Monta o conteúdo (foto do momento) de cada documento e gera PDFs."""
import base64
import mimetypes
from datetime import date
from decimal import Decimal
from functools import lru_cache

from administracao import configuracao
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.utils.formats import date_format

from core.formatos import data_extenso

from . import regras

CHAVES_ESCOLA = [
    "nome", "cnpj", "inep", "mantenedora", "endereco", "cidade", "telefone",
    "ato_autorizacao", "diretor", "diretor_ato", "secretario", "secretario_ato",
]


# ---------- formatação ----------
def data_curta(d):
    return date_format(d, "d/m/Y") if d else ""




def juntar(nomes):
    nomes = [n for n in nomes if n]
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def pct_texto(valor):
    return "" if valor is None else f"{valor:.1f}".replace(".", ",")


# ---------- blocos comuns ----------
def dados_escola():
    cfg = configuracao.escola()
    return {k: cfg.get(k, "") for k in CHAVES_ESCOLA}


def filiacao_texto(aluno):
    resp = list(aluno.responsaveis.all())
    pais = [r for r in resp if r.parentesco == "pai"] + [r for r in resp if r.parentesco == "mae"]
    if pais:
        return "filho(a) de " + juntar([r.nome for r in pais])
    legais = [r for r in resp if r.responsavel_legal] or resp
    if not legais:
        return ""
    return "sob a responsabilidade de " + juntar(
        [f"{r.nome} ({r.get_parentesco_display().lower()})" for r in legais]
    )


def dados_aluno(aluno):
    return {
        "nome": aluno.nome,
        "nascimento": data_curta(aluno.data_nascimento),
        "naturalidade": aluno.naturalidade,
        "filiacao_texto": filiacao_texto(aluno),
        "certidao": aluno.certidao_nascimento,
        "cpf": aluno.cpf,
    }


def dados_matricula(m):
    return {
        "ano": str(m.ano_letivo.ano),  # texto: evita o separador de milhar (2.026)
        "turma": m.turma.nome,
        "turno": m.get_turno_display(),
        "etapa": m.etapa,
        "etapa_nome": m.turma.get_etapa_display(),
        "infantil": regras.eh_infantil(m.etapa),
        "situacao": m.get_situacao_display(),
        "data_matricula": data_curta(m.data_matricula),
    }


def _base(aluno):
    escola = dados_escola()
    return {
        "escola": escola,
        "aluno": dados_aluno(aluno),
        "local_data": f"{escola['cidade'] or '______________'}, {data_extenso(date.today())}",
    }


def periodo_escolar(m):
    """Linha do histórico para uma matrícula (usa o registro escolar, se houver)."""
    p = dados_matricula(m)
    registro = getattr(m, "registro", None)
    p.update({"carga_horaria": "", "dias_letivos": "", "faltas": "", "frequencia": "",
              "resultado": "Sem registro", "parecer": "", "componentes": []})
    if registro:
        p.update({
            "carga_horaria": registro.carga_horaria or "",
            "dias_letivos": registro.dias_letivos if registro.dias_letivos is not None else "",
            "faltas": registro.faltas if registro.faltas is not None else "",
            "frequencia": pct_texto(registro.frequencia),
            "resultado": registro.get_resultado_display(),
            "parecer": registro.parecer,
            "componentes": [
                {"nome": c.nome, "carga_horaria": c.carga_horaria or "", "resultado": c.resultado}
                for c in registro.componentes.all()
            ],
        })
    return p


def _periodos(aluno):
    from matriculas.models import Matricula  # evita import circular na carga dos apps

    ms = (Matricula.objects.filter(aluno=aluno)
          .select_related("ano_letivo", "turma", "registro")
          .prefetch_related("registro__componentes")
          .order_by("ano_letivo__ano", "data_matricula"))
    return [periodo_escolar(m) for m in ms]


# ---------- construtores ----------
def construir_declaracao_matricula(m, finalidade=""):
    c = _base(m.aluno)
    c.update({"matricula": dados_matricula(m), "finalidade": finalidade.strip()})
    return c


def construir_declaracao_frequencia(m, inicio, fim, dias, faltas, observacoes=""):
    c = _base(m.aluno)
    presencas = dias - faltas
    pct = (Decimal(presencas) / Decimal(dias) * 100) if dias else None
    c.update({
        "matricula": dados_matricula(m),
        "periodo_inicio": data_curta(inicio), "periodo_fim": data_curta(fim),
        "dias_letivos": dias, "faltas": faltas, "presencas": presencas,
        "frequencia": pct_texto(pct), "observacoes": observacoes.strip(),
    })
    return c


def construir_historico(aluno, observacoes=""):
    c = _base(aluno)
    periodos = _periodos(aluno)
    tem_fund = any(not p["infantil"] for p in periodos)
    c.update({
        "titulo": "Histórico escolar" if tem_fund else "Ficha de registros escolares — Educação Infantil",
        "periodos": periodos,
        "tem_fundamental": tem_fund,
        "nota_infantil": regras.NOTA_INFANTIL if any(p["infantil"] for p in periodos) else "",
        "observacoes": observacoes.strip(),
    })
    return c


def construir_transferencia(m, data_saida, destino="", motivo="", observacoes=""):
    c = _base(m.aluno)
    periodos = _periodos(m.aluno)
    c.update({
        "matricula": dados_matricula(m),
        "data_saida": data_curta(data_saida),
        "destino": destino.strip(), "motivo": motivo.strip(),
        "periodos": periodos,
        "nota_infantil": regras.NOTA_INFANTIL if any(p["infantil"] for p in periodos) else "",
        "observacoes": observacoes.strip(),
    })
    return c


# ---------- PDF ----------
@lru_cache(maxsize=1)
def pdf_disponivel():
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:  # biblioteca ou dependências do sistema ausentes
        return False


def _data_uri(caminho):
    tipo = mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
    with open(caminho, "rb") as f:
        return f"data:{tipo};base64," + base64.b64encode(f.read()).decode()


def _foto_uri(aluno):
    try:
        return _data_uri(aluno.foto.path) if aluno.foto else ""
    except (OSError, ValueError):
        return ""


def contexto_pdf(aluno=None, extras=()):
    """CSS e imagens embutidos, para o PDF não depender de URLs."""
    css = "\n".join(
        open(finders.find(arq), encoding="utf-8").read() for arq in ("css/documento.css", *extras)
    )
    return {
        "pdf": True, "css_inline": css,
        "logo_src": _data_uri(finders.find("img/logo-doc.png")),
        "foto_src": _foto_uri(aluno) if aluno else "",
    }


def renderizar_pdf(template, contexto, request):
    import weasyprint

    html = render_to_string(template, contexto, request=request)
    return weasyprint.HTML(string=html).write_pdf()


# ---------- folha de ponto ----------
DIAS_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_ROTULO_CATEGORIA = {
    "feriado_nacional": "Feriado", "feriado_estadual": "Feriado", "feriado_municipal": "Feriado",
    "ponto_facultativo": "Ponto facultativo", "feriado_escolar": "Feriado escolar", "recesso": "Recesso",
}


def dias_do_mes_para_ponto(ano, mes, marcar_feriados=True, sabados=False):
    """Uma linha por dia do mês: fim de semana e (se pedido) feriados/recessos do calendário vêm marcados."""
    import calendar as _cal

    from calendario.models import Evento

    ultimo = _cal.monthrange(ano, mes)[1]
    rotulos = {}
    if marcar_feriados:
        eventos = Evento.objects.filter(
            sem_aula=True, categoria__in=list(_ROTULO_CATEGORIA),
            data_inicio__lte=date(ano, mes, ultimo)).prefetch_related("turmas")
        for ev in eventos:
            if ev.ultimo_dia < date(ano, mes, 1) or ev.turmas.all():
                continue
            for d in ev.dias():
                if d.year == ano and d.month == mes:
                    texto = f"{_ROTULO_CATEGORIA[ev.categoria]}: {ev.titulo}"
                    rotulos[d] = f"{rotulos[d]}; {texto}" if d in rotulos else texto
    linhas = []
    for dia in range(1, ultimo + 1):
        d = date(ano, mes, dia)
        sem = d.weekday()
        fechado = sem == 6 or (sem == 5 and not sabados)
        rotulo = ""
        if fechado:
            rotulo = DIAS_CURTOS[sem].replace("Sáb", "Sábado").replace("Dom", "Domingo")
        elif d in rotulos:
            rotulo = rotulos[d]
        linhas.append({"dia": dia, "semana": DIAS_CURTOS[sem], "fechado": fechado or d in rotulos, "rotulo": rotulo,
                       "fds": sem >= 5})
    return linhas
