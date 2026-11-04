from django import forms

from alunos.models import Aluno
from alunos.widgets import AlunoAutocompleteWidget


class BuscaAlunoForm(forms.Form):
    aluno = forms.ModelChoiceField(
        queryset=Aluno.objects.all(), widget=AlunoAutocompleteWidget, label="Aluno",
        error_messages={"required": "Escolha um aluno da lista."},
    )
