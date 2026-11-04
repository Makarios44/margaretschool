"""Feriados e datas do calendário escolar.

Nacionais: definidos em lei (fixos) + Sexta-feira Santa, que depende da Páscoa.
Pontos facultativos nacionais: Carnaval, Quarta-feira de Cinzas e Corpus Christi.
Estaduais e municipais: tabelas abaixo (conferidas com o Decreto estadual nº 35.209/2025 do RN, que
lista os feriados de 2026 para Natal). Outras cidades: cadastre os municipais pela tela de eventos.
"""
import unicodedata
from datetime import date, timedelta

from .models import Categoria as C

# (mês, dia, nome)
ESTADUAIS = {
    "RN": [(10, 3, "Mártires de Cunhaú e Uruaçu")],
}
# (mês, dia, nome) por (UF, município)
MUNICIPAIS = {
    ("RN", "natal"): [
        (1, 6, "Dia de Reis"),
        (11, 21, "Nossa Senhora da Apresentação (Padroeira de Natal)"),
    ],
}


def _chave(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


def municipios_cadastrados():
    return sorted(m.title() for (_uf, m) in MUNICIPAIS)


def tem_municipais(uf, municipio):
    return (uf.upper(), _chave(municipio)) in MUNICIPAIS


def pascoa(ano):
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def _n_esimo_dia_da_semana(ano, mes, dia_semana, n):
    """n-ésimo `dia_semana` (0=segunda … 6=domingo) do mês."""
    d = date(ano, mes, 1)
    d += timedelta(days=(dia_semana - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _item(data, titulo, categoria, sem_aula, descricao="", repete=False):
    return {"data": data, "titulo": titulo, "categoria": categoria, "sem_aula": sem_aula,
            "descricao": descricao, "repete": repete}


def nacionais(ano):
    p = pascoa(ano)
    itens = [
        (date(ano, 1, 1), "Confraternização Universal"),
        (p - timedelta(days=2), "Sexta-feira Santa (Paixão de Cristo)"),
        (date(ano, 4, 21), "Tiradentes"),
        (date(ano, 5, 1), "Dia do Trabalho"),
        (date(ano, 9, 7), "Independência do Brasil"),
        (date(ano, 10, 12), "Nossa Senhora Aparecida"),
        (date(ano, 11, 2), "Finados"),
        (date(ano, 11, 15), "Proclamação da República"),
        (date(ano, 12, 25), "Natal"),
    ]
    if ano >= 2024:  # Lei 14.759/2023
        itens.append((date(ano, 11, 20), "Dia Nacional de Zumbi e da Consciência Negra"))
    return [_item(d, t, C.FERIADO_NACIONAL, True) for d, t in sorted(itens)]


def pontos_facultativos(ano):
    p = pascoa(ano)
    return [
        _item(p - timedelta(days=48), "Carnaval (segunda-feira)", C.PONTO_FACULTATIVO, True,
              "Ponto facultativo: a escola decide se há aula."),
        _item(p - timedelta(days=47), "Carnaval (terça-feira)", C.PONTO_FACULTATIVO, True,
              "Ponto facultativo: a escola decide se há aula."),
        _item(p - timedelta(days=46), "Quarta-feira de Cinzas", C.PONTO_FACULTATIVO, False,
              "Ponto facultativo até as 14h."),
        _item(p + timedelta(days=60), "Corpus Christi", C.PONTO_FACULTATIVO, True,
              "Ponto facultativo: a escola decide se há aula."),
    ]


def estaduais(ano, uf):
    return [_item(date(ano, m, d), nome, C.FERIADO_ESTADUAL, True, repete=False)
            for m, d, nome in ESTADUAIS.get(uf.upper(), [])]


def municipais(ano, uf, municipio):
    lista = MUNICIPAIS.get((uf.upper(), _chave(municipio)), [])
    return [_item(date(ano, m, d), nome, C.FERIADO_MUNICIPAL, True) for m, d, nome in lista]


def comemorativas(ano):
    p = pascoa(ano)
    return [
        _item(p, "Páscoa", C.COMEMORATIVA, False),
        _item(_n_esimo_dia_da_semana(ano, 5, 6, 2), "Dia das Mães", C.COMEMORATIVA, False),
        _item(date(ano, 6, 24), "Dia de São João", C.COMEMORATIVA, False),
        _item(date(ano, 6, 29), "Dia de São Pedro", C.COMEMORATIVA, False),
        _item(_n_esimo_dia_da_semana(ano, 8, 6, 2), "Dia dos Pais", C.COMEMORATIVA, False),
        _item(date(ano, 8, 22), "Dia do Folclore", C.COMEMORATIVA, False),
        _item(date(ano, 10, 15), "Dia do Professor", C.FERIADO_ESCOLAR, True,
              "Feriado escolar (Decreto federal nº 52.682/1963)."),
    ]


def gerar(ano, uf, municipio, incluir_comemorativas=True):
    itens = nacionais(ano) + pontos_facultativos(ano) + estaduais(ano, uf) + municipais(ano, uf, municipio)
    if incluir_comemorativas:
        itens += comemorativas(ano)
    return sorted(itens, key=lambda i: (i["data"], i["titulo"]))
