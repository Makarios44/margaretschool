from datetime import date

from django import forms
from django.db.models import Q

from alunos.models import Aluno  # noqa: F401  (mantém ordem de apps)
from core.forms import BootstrapFormMixin
from matriculas.models import Matricula

from .models import CategoriaDespesa, Cobranca, Despesa

MESES = [
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"), (5, "Maio"), (6, "Junho"),
    (7, "Julho"), (8, "Agosto"), (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
]
DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class CobrancaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Cobranca
        fields = ["matricula", "tipo", "descricao", "vencimento", "valor", "desconto",
                  "motivo_desconto", "observacoes"]
        widgets = {
            "vencimento": DATA,
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["matricula"].queryset = Matricula.objects.select_related(
            "aluno", "ano_letivo"
        ).order_by("aluno__nome", "-ano_letivo__ano")
        self.fields["desconto"].required = False
        if self.instance.pk:
            self.fields["matricula"].disabled = True

    def clean_desconto(self):
        return self.cleaned_data.get("desconto") or 0


class PagamentoForm(BootstrapFormMixin, forms.Form):
    data_pagamento = forms.DateField(label="Data do pagamento", widget=DATA)
    forma_pagamento = forms.ChoiceField(
        label="Forma de pagamento", choices=[("", "Selecione…")] + Cobranca.Forma.choices
    )
    desconto = forms.DecimalField(
        label="Desconto / abatimento (R$)", min_value=0, max_digits=8, decimal_places=2,
        required=False,
    )
    multa = forms.DecimalField(label="Multa (R$)", min_value=0, max_digits=8, decimal_places=2, required=False)
    juros = forms.DecimalField(label="Juros (R$)", min_value=0, max_digits=8, decimal_places=2, required=False)
    observacoes = forms.CharField(label="Observações", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, cobranca, **kwargs):
        super().__init__(*args, **kwargs)
        self.cobranca = cobranca

    def clean_data_pagamento(self):
        data = self.cleaned_data["data_pagamento"]
        if data > date.today():
            raise forms.ValidationError("A data do pagamento não pode ser no futuro.")
        return data

    def clean_desconto(self):
        desc = self.cleaned_data.get("desconto") or 0
        if desc > self.cobranca.valor:
            raise forms.ValidationError("O desconto não pode ser maior que o valor da cobrança.")
        return desc

    def clean_multa(self):
        return self.cleaned_data.get("multa") or 0

    def clean_juros(self):
        return self.cleaned_data.get("juros") or 0


class GerarMensalidadesForm(BootstrapFormMixin, forms.Form):
    mes_inicial = forms.TypedChoiceField(label="Primeira mensalidade", choices=MESES, coerce=int)
    quantidade = forms.IntegerField(label="Quantas mensalidades", min_value=1, max_value=12)
    incluir_taxa = forms.BooleanField(label="Gerar também a taxa de matrícula", required=False)

    def __init__(self, *args, mostrar_taxa=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not mostrar_taxa:
            del self.fields["incluir_taxa"]

    def clean(self):
        dados = super().clean()
        ini, qtd = dados.get("mes_inicial"), dados.get("quantidade")
        if ini and qtd and ini + qtd - 1 > 12:
            raise forms.ValidationError(
                "As mensalidades não podem passar de dezembro. Diminua a quantidade ou antecipe o mês inicial."
            )
        return dados


class DespesaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ["data", "descricao", "categoria", "valor", "fornecedor", "forma_pagamento",
                  "numero_documento", "comprovante", "observacoes"]
        widgets = {
            "data": DATA, "observacoes": forms.Textarea(attrs={"rows": 2}),
            "comprovante": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.webp,image/*,application/pdf"}),
        }

    TAMANHO_MAXIMO = 5 * 1024 * 1024

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ativas = CategoriaDespesa.objects.filter(ativa=True)
        if self.instance.pk:  # mantém a categoria atual mesmo que tenha sido desativada depois
            ativas = CategoriaDespesa.objects.filter(Q(ativa=True) | Q(pk=self.instance.categoria_id))
        self.fields["categoria"].queryset = ativas
        self.fields["categoria"].empty_label = "Escolha a categoria…"
        self.fields["forma_pagamento"].choices = [("", "Escolha…")] + list(Despesa.Forma.choices)

    def clean_data(self):
        data = self.cleaned_data["data"]
        if data > date.today():
            raise forms.ValidationError("A data do gasto não pode ser no futuro.")
        return data

    def clean_comprovante(self):
        arquivo = self.cleaned_data.get("comprovante")
        if arquivo and hasattr(arquivo, "size") and arquivo.size > self.TAMANHO_MAXIMO:
            raise forms.ValidationError("O arquivo é maior que 5 MB. Envie uma foto ou PDF menor.")
        return arquivo
