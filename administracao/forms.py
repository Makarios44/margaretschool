from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from core.forms import BootstrapFormMixin
from financeiro.models import CategoriaDespesa
from matriculas.models import AnoLetivo, Turma

from .models import ConfiguracaoEscola

User = get_user_model()


class EscolaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoEscola
        exclude = ["atualizado_em"]


class AnoLetivoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AnoLetivo
        fields = ["ano", "atual"]

    def clean_ano(self):
        ano = self.cleaned_data["ano"]
        if not 2000 <= ano <= 2100:
            raise forms.ValidationError("Informe um ano entre 2000 e 2100.")
        return ano


class TurmaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["nome", "ano_letivo", "turno", "etapa", "vagas"]


PERFIS = [
    ("familia", "Família ou professor — vê só o painel e o calendário"),
    ("secretaria", "Secretaria — alunos, matrículas, financeiro, documentos e calendário"),
    ("admin", "Administrador — tudo, inclusive usuários e dados da escola"),
]


def perfil_do_usuario(u):
    return "admin" if u.is_superuser else ("secretaria" if u.is_staff else "familia")


def ultimo_administrador(usuario):
    """True se este é o único administrador ativo (não pode ser rebaixado nem desativado)."""
    return (usuario.is_superuser and usuario.is_active
            and not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=usuario.pk).exists())


class UsuarioForm(BootstrapFormMixin, forms.ModelForm):
    perfil = forms.ChoiceField(label="Perfil de acesso", choices=PERFIS, widget=forms.RadioSelect)
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), required=False)
    password2 = forms.CharField(label="Repita a senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), required=False)
    enviar_convite = forms.BooleanField(
        label="Enviar convite por e-mail (a pessoa cria a própria senha)", required=False,
        help_text="Se marcar, não precisa digitar senha: a pessoa recebe um link por e-mail para criá-la.")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        labels = {"username": "Usuário (para entrar)", "first_name": "Nome", "last_name": "Sobrenome", "email": "E-mail"}
        help_texts = {"username": "Letras, números e @/./+/-/_ . Sem espaços."}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.criando = self.instance.pk is None
        self.fields["perfil"].widget.attrs["class"] = "form-check-input"
        if self.criando:
            self.fields["password1"].required = False
            self.fields["password2"].required = False
            self.initial.setdefault("perfil", "secretaria")
        else:
            del self.fields["password1"], self.fields["password2"], self.fields["enviar_convite"]
            self.initial["perfil"] = perfil_do_usuario(self.instance)

    def clean(self):
        d = super().clean()
        perfil = d.get("perfil")
        if not self.criando and perfil and perfil != "admin" and self.instance.is_superuser:
            if self.editor and self.editor.pk == self.instance.pk:
                self.add_error("perfil", "Você não pode tirar o seu próprio acesso de administrador.")
            elif ultimo_administrador(self.instance):
                self.add_error("perfil", "Este é o único administrador. Torne outro usuário administrador antes.")
        email = (d.get("email") or "").strip()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            self.add_error("email", "Já existe um usuário com este e-mail.")
        if self.criando:
            s1, s2 = d.get("password1"), d.get("password2")
            if d.get("enviar_convite"):
                if not email:
                    self.add_error("email", "Informe o e-mail para enviar o convite.")
                return d
            if not s1:
                self.add_error("password1", "Digite uma senha ou marque “Enviar convite por e-mail”.")
            if not s2 and s1:
                self.add_error("password2", "Repita a senha.")
            if s1 and s2 and s1 != s2:
                self.add_error("password2", "As senhas não são iguais.")
            elif s1:
                tentativa = User(username=d.get("username", ""), first_name=d.get("first_name", ""),
                                 last_name=d.get("last_name", ""), email=d.get("email", ""))
                try:
                    validate_password(s1, tentativa)
                except forms.ValidationError as erro:
                    self.add_error("password1", erro)
        return d

    def save(self, commit=True):
        usuario = super().save(commit=False)
        perfil = self.cleaned_data["perfil"]
        usuario.is_superuser = perfil == "admin"
        usuario.is_staff = perfil in ("admin", "secretaria")
        if self.criando:
            if self.cleaned_data.get("enviar_convite"):
                usuario.set_unusable_password()
            else:
                usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
        return usuario


class SenhaForm(BootstrapFormMixin, forms.Form):
    password1 = forms.CharField(label="Nova senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Repita a nova senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

    def clean(self):
        d = super().clean()
        s1, s2 = d.get("password1"), d.get("password2")
        if s1 and s2 and s1 != s2:
            self.add_error("password2", "As senhas não são iguais.")
        elif s1:
            try:
                validate_password(s1, self.usuario)
            except forms.ValidationError as erro:
                self.add_error("password1", erro)
        return d


class CategoriaDespesaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CategoriaDespesa
        fields = ["nome", "ativa"]
