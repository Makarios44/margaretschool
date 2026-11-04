from django import forms
from django.forms import inlineformset_factory

from core.forms import BootstrapFormMixin, BootstrapInlineFormSet
from matriculas.models import AnoLetivo, Turma

from .models import Evento, PeriodoLetivo

DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
HORA = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class EventoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Evento
        fields = ["titulo", "categoria", "data_inicio", "data_fim", "hora_inicio", "hora_fim", "local",
                  "descricao", "sem_aula", "publico", "turmas", "repete_anualmente"]
        widgets = {
            "data_inicio": DATA, "data_fim": DATA, "hora_inicio": HORA, "hora_fim": HORA,
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "turmas": forms.SelectMultiple(attrs={"size": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turmas"].queryset = Turma.objects.select_related("ano_letivo")


class AnoLetivoConfigForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AnoLetivo
        fields = ["inicio_aulas", "fim_aulas", "horas_dia_letivo"]
        widgets = {"inicio_aulas": DATA, "fim_aulas": DATA}

    def clean(self):
        d = super().clean()
        ini, fim = d.get("inicio_aulas"), d.get("fim_aulas")
        if bool(ini) != bool(fim):
            raise forms.ValidationError("Informe o início e o fim das aulas (ou deixe os dois em branco).")
        if ini and fim and fim < ini:
            self.add_error("fim_aulas", "O fim das aulas deve ser depois do início.")
        return d


class PeriodoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PeriodoLetivo
        fields = ["nome", "inicio", "fim"]
        widgets = {"inicio": DATA, "fim": DATA}


PeriodoFormSet = inlineformset_factory(
    AnoLetivo, PeriodoLetivo, form=PeriodoForm, formset=BootstrapInlineFormSet,
    extra=0, can_delete=True,
)
