from django import forms

from alunos.models import Aluno
from alunos.widgets import AlunoAutocompleteWidget
from core.forms import BootstrapFormMixin

from .models import Matricula, Turma


class MatriculaForm(BootstrapFormMixin, forms.ModelForm):
    aluno = forms.ModelChoiceField(
        queryset=Aluno.objects.all(), widget=AlunoAutocompleteWidget, label="Aluno",
        error_messages={"required": "Escolha o aluno na lista que aparece enquanto você digita."},
    )

    class Meta:
        model = Matricula
        fields = [
            "aluno", "ano_letivo", "turma", "tipo", "data_matricula", "situacao",
            "taxa_matricula", "taxa_paga", "mensalidade", "dia_vencimento",
            "desconto_percentual", "desconto_motivo", "observacoes",
        ]
        widgets = {
            "data_matricula": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turma"].queryset = Turma.objects.select_related("ano_letivo")
        self.fields["turma"].help_text = "O turno é definido pela turma escolhida."
        self.fields["desconto_percentual"].required = False
        if self.instance.pk:  # na edição, aluno e ano não mudam
            self.fields["aluno"].disabled = True
            self.fields["ano_letivo"].disabled = True

    def clean_desconto_percentual(self):
        return self.cleaned_data.get("desconto_percentual") or 0
