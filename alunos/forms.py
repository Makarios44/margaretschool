from datetime import date

from django import forms
from django.forms import inlineformset_factory

from core.forms import BootstrapFormMixin, BootstrapInlineFormSet

from .models import Aluno, ContatoEmergencia, Responsavel


class AlunoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Aluno
        fields = [
            "nome", "data_nascimento", "sexo", "naturalidade", "cpf", "certidao_nascimento",
            "endereco", "bairro", "cidade", "foto", "alergias", "observacoes_cuidado",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "foto": forms.FileInput(attrs={"accept": "image/*"}),
            "alergias": forms.Textarea(attrs={"rows": 3}),
            "observacoes_cuidado": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_data_nascimento(self):
        nasc = self.cleaned_data["data_nascimento"]
        if nasc > date.today():
            raise forms.ValidationError("A data de nascimento não pode ser no futuro.")
        return nasc


class ResponsavelForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Responsavel
        fields = [
            "nome", "parentesco", "cpf", "telefone", "email", "profissao",
            "responsavel_legal", "responsavel_financeiro",
        ]


class ContatoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ContatoEmergencia
        fields = ["nome", "parentesco", "telefone", "autorizado_buscar"]


class ResponsavelBaseFormSet(BootstrapInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "error_messages", {"too_few_forms": "Informe ao menos um responsável."}
        )
        super().__init__(*args, **kwargs)


class ContatoBaseFormSet(BootstrapInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "error_messages",
            {"too_few_forms": "Informe ao menos um contato de emergência."},
        )
        super().__init__(*args, **kwargs)


ResponsavelFormSet = inlineformset_factory(
    Aluno, Responsavel, form=ResponsavelForm, formset=ResponsavelBaseFormSet,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)
ContatoFormSet = inlineformset_factory(
    Aluno, ContatoEmergencia, form=ContatoForm, formset=ContatoBaseFormSet,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)
