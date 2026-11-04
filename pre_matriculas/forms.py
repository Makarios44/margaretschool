from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from core.forms import BootstrapFormMixin
from matriculas.models import Turma

from .models import SolicitacaoPreMatricula


class SolicitacaoPreMatriculaForm(BootstrapFormMixin, forms.ModelForm):
    confirmar_dados = forms.BooleanField(
        label="Confirmo que as informações fornecidas são verdadeiras e autorizo seu uso para análise da pré-matrícula.",
        required=True,
    )

    class Meta:
        model = SolicitacaoPreMatricula
        fields = [
            "nome_crianca", "data_nascimento", "sexo", "naturalidade", "certidao_nascimento",
            "endereco", "bairro", "cidade", "alergias", "observacoes_cuidado",
            "nome_responsavel", "parentesco", "cpf_responsavel", "telefone", "email", "profissao",
            "responsavel_legal", "responsavel_financeiro",
            "contato_emergencia_nome", "contato_emergencia_parentesco", "contato_emergencia_telefone",
            "contato_pode_buscar", "turma_desejada", "observacoes_familia",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "alergias": forms.Textarea(attrs={"rows": 2}),
            "observacoes_cuidado": forms.Textarea(attrs={"rows": 2}),
            "observacoes_familia": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, ano_letivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            "nome_crianca", "data_nascimento", "sexo", "naturalidade", "certidao_nascimento",
            "endereco", "bairro", "cidade", "alergias", "observacoes_cuidado",
            "nome_responsavel", "parentesco", "cpf_responsavel", "telefone", "email", "profissao",
            "responsavel_legal", "responsavel_financeiro",
            "contato_emergencia_nome", "contato_emergencia_parentesco", "contato_emergencia_telefone",
            "contato_pode_buscar", "turma_desejada", "observacoes_familia", "confirmar_dados",
        ])
        for campo in ("contato_emergencia_nome", "contato_emergencia_parentesco", "contato_emergencia_telefone"):
            self.fields[campo].required = True
        self.fields["turma_desejada"].required = False
        if ano_letivo:
            self.fields["turma_desejada"].queryset = Turma.objects.filter(ano_letivo=ano_letivo).order_by("nome", "turno")
            self.fields["turma_desejada"].help_text = "A preferência será analisada pela secretaria e não garante vaga."
        self.fields["responsavel_legal"].initial = True
        self.fields["responsavel_financeiro"].initial = True

    def clean_data_nascimento(self):
        nascimento = self.cleaned_data["data_nascimento"]
        if nascimento > date.today():
            raise ValidationError("A data de nascimento não pode estar no futuro.")
        return nascimento


class AprovarPreMatriculaForm(BootstrapFormMixin, forms.Form):
    turma = forms.ModelChoiceField(queryset=Turma.objects.none(), label="Turma confirmada")
    mensalidade = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0, label="Mensalidade (R$)")
    taxa_matricula = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0, initial=0, label="Taxa de matrícula (R$)")
    dia_vencimento = forms.IntegerField(min_value=1, max_value=28, initial=10, label="Dia de vencimento")
    tipo = forms.ChoiceField(choices=(("nova", "Matrícula nova"), ("rematricula", "Rematrícula")), initial="nova", label="Tipo")
    usar_aluno_existente = forms.BooleanField(
        required=False, label="Usar o cadastro existente deste aluno (não criar outro)",
        help_text="Só aparece quando já existe um aluno com o mesmo nome e data de nascimento.",
    )

    def __init__(self, *args, ano_letivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Turma.objects.select_related("ano_letivo").order_by("nome", "turno")
        if ano_letivo:
            qs = qs.filter(ano_letivo=ano_letivo)
        self.fields["turma"].queryset = qs
