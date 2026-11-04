from django import template

register = template.Library()


@register.filter
def get_item(dicionario, chave):
    return dicionario.get(chave, "")


DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


@register.filter
def data_longa(d):
    """terça-feira, 6 de janeiro de 2026"""
    from core.formatos import data_extenso

    return f"{DIAS[d.weekday()]}, {data_extenso(d)}"
