"""Valor monetário por extenso (para recibos). Ex.: 1234.56 -> 'mil duzentos e trinta e quatro reais e cinquenta e seis centavos'."""
from decimal import ROUND_HALF_UP, Decimal

_UNID = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
         "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
         "dezoito", "dezenove"]
_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CENT = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
         "setecentos", "oitocentos", "novecentos"]


def _ate_999(n):
    if n == 100:
        return "cem"
    c, r = divmod(n, 100)
    partes = []
    if c:
        partes.append(_CENT[c])
    if r:
        if r < 20:
            partes.append(_UNID[r])
        else:
            d, u = divmod(r, 10)
            partes.append(_DEZ[d] + (f" e {_UNID[u]}" if u else ""))
    return " e ".join(partes)


def _inteiro(n):
    if n == 0:
        return "zero"
    milhoes, resto = divmod(n, 1_000_000)
    milhares, unidades = divmod(resto, 1000)
    grupos = []  # (texto, valor do grupo)
    if milhoes:
        grupos.append(("um milhão" if milhoes == 1 else f"{_ate_999(milhoes)} milhões", milhoes))
    if milhares:
        grupos.append(("mil" if milhares == 1 else f"{_ate_999(milhares)} mil", milhares))
    if unidades:
        grupos.append((_ate_999(unidades), unidades))
    texto = grupos[0][0]
    for i in range(1, len(grupos)):
        # "e" só antes do último grupo, quando ele é menor que 100 ou múltiplo de 100
        ultimo = i == len(grupos) - 1
        valor = grupos[i][1]
        sep = " e " if ultimo and (valor < 100 or valor % 100 == 0) else " "
        texto += sep + grupos[i][0]
    return texto


def valor_por_extenso(valor):
    valor = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    reais, centavos = divmod(int(valor * 100), 100)
    partes = []
    if reais:
        sufixo = "real" if reais == 1 else ("de reais" if reais % 1_000_000 == 0 else "reais")
        partes.append(f"{_inteiro(reais)} {sufixo}")
    if centavos:
        partes.append(f"{_inteiro(centavos)} {'centavo' if centavos == 1 else 'centavos'}")
    return " e ".join(partes) or "zero real"
