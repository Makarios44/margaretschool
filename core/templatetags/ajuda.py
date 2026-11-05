import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def botoes(texto):
    """Texto entre [colchetes] vira um 'botão' desenhado, para a pessoa reconhecer na tela. O resto é escapado."""
    seguro = conditional_escape(texto)
    return mark_safe(re.sub(r"\[([^\]]+)\]", r'<span class="tecla">\1</span>', str(seguro)))
