from datetime import date

from django import forms
from django.forms import inlineformset_factory

from core.forms import BootstrapFormMixin, BootstrapInlineFormSet
from matriculas.models import Matricula

from . import regras
from .models import ComponenteRegistro, RegistroEscolar

DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class _MatriculaChoice(forms.ModelChoiceField):
    def label_from_instance(self, m):
        return f"{m.ano_letivo} — {m.turma.nome} ({m.get_turno_display()}) — {m.get_situacao_display()}"


class _BaseDocForm(BootstrapFormMixin, forms.Form):
    """Formulário de documento ligado a uma matrícula do aluno."""

    situacoes = None  # None = qualquer situação

    def __init__(self, *args, aluno, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Matricula.objects.filter(aluno=aluno).select_related("ano_letivo", "turma")
        if self.situacoes:
            qs = qs.filter(situacao__in=self.situacoes)
        self.fields["matricula"] = _MatriculaChoice(
            queryset=qs.order_by("-ano_letivo__ano"), label="Matrícula", empty_label=None
        )
        self.order_fields(["matricula"])


class DeclaracaoMatriculaForm(_BaseDocForm):
    situacoes = [Matricula.Situacao.ATIVO]
    finalidade = forms.CharField(
        label="Finalidade (opcional)", required=False, max_length=120,
        help_text="Aparece como \"para fins de …\". Ex.: apresentação ao empregador, benefício social.",
    )


class DeclaracaoFrequenciaForm(_BaseDocForm):
    periodo_inicio = forms.DateField(label="Início do período", widget=DATA)
    periodo_fim = forms.DateField(label="Fim do período", widget=DATA)
    dias_letivos = forms.IntegerField(label="Dias letivos no período", min_value=1)
    faltas = forms.IntegerField(label="Faltas no período", min_value=0)
    observacoes = forms.CharField(label="Observações (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        d = super().clean()
        ini, fim = d.get("periodo_inicio"), d.get("periodo_fim")
        if ini and fim and ini > fim:
            self.add_error("periodo_fim", "O fim do período deve ser depois do início.")
        if fim and fim > date.today():
            self.add_error("periodo_fim", "O período não pode terminar no futuro.")
        if d.get("dias_letivos") is not None and d.get("faltas") is not None and d["faltas"] > d["dias_letivos"]:
            self.add_error("faltas", "As faltas não podem ser maiores que os dias letivos.")
        return d


class HistoricoForm(BootstrapFormMixin, forms.Form):
    observacoes = forms.CharField(
        label="Observações (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Ex.: estudos anteriores feitos em outra escola, adaptações, informações complementares.",
    )

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)


class TransferenciaForm(_BaseDocForm):
    situacoes = [Matricula.Situacao.ATIVO, Matricula.Situacao.TRANSFERIDO]
    data_saida = forms.DateField(label="Data da transferência", widget=DATA)
    escola_destino = forms.CharField(label="Escola de destino (opcional)", required=False, max_length=150)
    motivo = forms.CharField(label="Motivo (opcional)", required=False, max_length=150,
                             help_text="Ex.: mudança de cidade, mudança de endereço.")
    marcar_transferido = forms.BooleanField(
        label="Marcar a matrícula como \"Transferido\"", required=False, initial=True,
    )
    observacoes = forms.CharField(label="Observações (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean_data_saida(self):
        data = self.cleaned_data["data_saida"]
        if data > date.today():
            raise forms.ValidationError("A data da transferência não pode ser no futuro.")
        return data


class RegistroEscolarForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RegistroEscolar
        fields = ["carga_horaria", "dias_letivos", "faltas", "resultado", "parecer"]
        widgets = {"parecer": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, etapa, **kwargs):
        super().__init__(*args, **kwargs)
        if regras.eh_infantil(etapa):  # educação infantil não tem aprovação nem retenção
            bloqueados = {RegistroEscolar.Resultado.APROVADO, RegistroEscolar.Resultado.RETIDO}
            self.fields["resultado"].choices = [
                c for c in RegistroEscolar.Resultado.choices if c[0] not in bloqueados
            ]


class ComponenteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ComponenteRegistro
        fields = ["nome", "carga_horaria", "resultado"]


def componentes_formset(extra=0):
    return inlineformset_factory(
        RegistroEscolar, ComponenteRegistro, form=ComponenteForm,
        formset=BootstrapInlineFormSet, extra=extra, can_delete=True,
    )


MESES_NOMES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
               "Outubro", "Novembro", "Dezembro"]


class FolhaPontoForm(BootstrapFormMixin, forms.Form):
    professores = forms.CharField(
        label="Nome do(a) professor(a)", widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Um nome por linha"}),
        help_text="Para vários professores, escreva um nome por linha: sai uma folha para cada um.")
    mes = forms.TypedChoiceField(label="Mês", choices=list(enumerate(MESES_NOMES, 1)), coerce=int)
    ano = forms.IntegerField(label="Ano", min_value=2000, max_value=2100)
    cargo = forms.CharField(label="Cargo / função", max_length=60, initial="Professor(a)", required=False)
    turma_disciplina = forms.CharField(label="Turma / disciplina (opcional)", max_length=100, required=False)
    horario = forms.CharField(
        label="Horário de trabalho (opcional)", max_length=60, required=False,
        help_text="Ex.: 07:30 às 11:30. Só aparece no cabeçalho; os horários do dia são preenchidos à mão.")
    carga_semanal = forms.CharField(label="Carga horária semanal (opcional)", max_length=30, required=False)
    marcar_feriados = forms.BooleanField(
        label="Marcar feriados, pontos facultativos e recessos do calendário da escola", required=False, initial=True)
    sabados = forms.BooleanField(label="A escola funciona aos sábados (deixar os sábados para preencher)", required=False)

    def clean_professores(self):
        nomes, vistos = [], set()
        for linha in self.cleaned_data["professores"].splitlines():
            nome = " ".join(linha.split())
            if nome and nome.lower() not in vistos:
                vistos.add(nome.lower())
                nomes.append(nome)
        if not nomes:
            raise forms.ValidationError("Informe ao menos um nome.")
        if len(nomes) > 40:
            raise forms.ValidationError("Informe no máximo 40 nomes por vez.")
        if any(len(n) > 120 for n in nomes):
            raise forms.ValidationError("Cada nome pode ter no máximo 120 caracteres.")
        return nomes
