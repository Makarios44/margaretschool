from django import forms
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Aluno
from .utils import resumo_aluno


class AlunoAutocompleteWidget(forms.Widget):
    """Campo de aluno por digitação: sugere nomes conforme se escreve e guarda só o id escolhido."""

    def use_required_attribute(self, initial):
        return False  # o campo visível não é o que vai no envio

    def id_for_label(self, id_):
        return f"{id_}_busca"

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        aluno = None
        if value not in (None, ""):
            try:
                aluno = Aluno.objects.filter(pk=value).first()
            except (TypeError, ValueError):
                aluno = None
        return mark_safe(render_to_string("partials/aluno_autocomplete.html", {
            "name": name, "id": attrs.get("id", f"id_{name}"), "aluno": aluno,
            "detalhe": resumo_aluno(aluno)["detalhe"] if aluno else "",
            "desativado": bool(attrs.get("disabled")),
            "url": reverse("aluno_buscar"), "url_novo": reverse("aluno_create"),
        }))
