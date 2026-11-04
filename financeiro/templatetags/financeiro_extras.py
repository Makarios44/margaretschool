from django import template

from core.formatos import data_extenso as _data_extenso
from financeiro.extenso import valor_por_extenso

register = template.Library()


@register.filter
def extenso(valor):
    return valor_por_extenso(valor)


@register.filter
def data_extenso(data):
    return _data_extenso(data)
