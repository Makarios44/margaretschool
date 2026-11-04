from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.mixins import staff_required, superuser_required
from matriculas.models import AnoLetivo, Matricula, Turma

from . import configuracao
from financeiro.models import CategoriaDespesa
from .forms import AnoLetivoForm, CategoriaDespesaForm, EscolaForm, SenhaForm, TurmaForm, UsuarioForm, perfil_do_usuario, ultimo_administrador
from .models import ConfiguracaoEscola

User = get_user_model()


def _form_generico(request, form, titulo, voltar, subtitulo="", enctype=False, extra=None):
    ctx = {"form": form, "titulo": titulo, "voltar": voltar, "subtitulo": subtitulo}
    ctx.update(extra or {})
    return render(request, "administracao/form.html", ctx)


@staff_required
def hub(request):
    return render(request, "administracao/hub.html", {
        "n_anos": AnoLetivo.objects.count(), "n_turmas": Turma.objects.count(),
        "n_usuarios": User.objects.filter(is_active=True).count() if request.user.is_superuser else None,
    })


# ---------- dados da escola ----------
@superuser_required
def escola_dados(request):
    obj = ConfiguracaoEscola.objects.first() or ConfiguracaoEscola()
    form = EscolaForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados da escola salvos. Os documentos novos já usam estas informações.")
        return redirect("adm_escola")
    padrao = configuracao.escola() | {"multa": configuracao.financeiro()["multa_percentual"],
                                      "juros": configuracao.financeiro()["juros_mensal_percentual"]}
    return render(request, "administracao/escola.html", {"form": form, "atual": padrao})


# ---------- anos letivos ----------
@staff_required
def anos_list(request):
    anos = AnoLetivo.objects.annotate(
        n_turmas=Count("turmas", distinct=True), n_matriculas=Count("matriculas", distinct=True))
    return render(request, "administracao/anos.html", {"anos": anos})


@staff_required
def ano_form(request, pk=None):
    ano = get_object_or_404(AnoLetivo, pk=pk) if pk else None
    form = AnoLetivoForm(request.POST or None, instance=ano)
    if request.method == "POST" and form.is_valid():
        ano = form.save()
        messages.success(request, f"Ano letivo {ano.ano} salvo.")
        return redirect("adm_anos")
    return _form_generico(
        request, form, "Editar ano letivo" if ano else "Novo ano letivo", "adm_anos",
        "Depois de criar, configure o início/fim das aulas e os bimestres na lista de anos.")


@staff_required
@require_POST
def ano_excluir(request, pk):
    ano = get_object_or_404(AnoLetivo, pk=pk)
    try:
        ano.delete()
        messages.success(request, f"Ano letivo {ano.ano} excluído.")
    except ProtectedError:
        messages.error(request, f"O ano {ano.ano} tem turmas ou matrículas e não pode ser excluído.")
    return redirect("adm_anos")


# ---------- turmas ----------
@staff_required
def turmas_list(request):
    anos = AnoLetivo.objects.all()
    if "ano" in request.GET:
        ano_id = request.GET["ano"]
    else:
        padrao = AnoLetivo.padrao()
        ano_id = str(padrao.pk) if padrao else ""
    turmas = Turma.objects.select_related("ano_letivo").annotate(
        ocupadas=Count("matriculas", filter=Q(matriculas__situacao=Matricula.Situacao.ATIVO)))
    if ano_id.isdigit():
        turmas = turmas.filter(ano_letivo_id=int(ano_id))
    return render(request, "administracao/turmas.html", {
        "turmas": turmas, "anos": anos, "ano_id": ano_id,
        "ano_sel": anos.filter(pk=ano_id).first() if ano_id.isdigit() else None,
    })


@staff_required
def turma_form(request, pk=None):
    turma = get_object_or_404(Turma, pk=pk) if pk else None
    inicial = None
    if not turma and AnoLetivo.padrao():
        inicial = {"ano_letivo": AnoLetivo.padrao()}
    form = TurmaForm(request.POST or None, instance=turma, initial=inicial)
    if request.method == "POST" and form.is_valid():
        turma = form.save()
        messages.success(request, f"Turma {turma.nome} salva.")
        return redirect(f"/administracao/turmas/?ano={turma.ano_letivo_id}")
    return _form_generico(
        request, form, "Editar turma" if turma else "Nova turma", "adm_turmas",
        "A etapa define o modelo dos documentos escolares (frequência, histórico, transferência).")


@staff_required
@require_POST
def turma_excluir(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    try:
        turma.delete()
        messages.success(request, f"Turma {turma.nome} excluída.")
    except ProtectedError:
        messages.error(request, f"A turma {turma.nome} tem matrículas e não pode ser excluída.")
    return redirect(f"/administracao/turmas/?ano={turma.ano_letivo_id}")


@staff_required
@require_POST
def turmas_copiar(request):
    """Copia as turmas de um ano para outro (nome, turno, etapa e vagas), sem repetir as que já existem."""
    origem = get_object_or_404(AnoLetivo, pk=request.POST.get("origem"))
    destino = get_object_or_404(AnoLetivo, pk=request.POST.get("destino"))
    if origem.pk == destino.pk:
        messages.error(request, "Escolha anos diferentes para copiar.")
        return redirect("adm_turmas")
    criadas = 0
    for t in Turma.objects.filter(ano_letivo=origem):
        _, novo = Turma.objects.get_or_create(
            nome=t.nome, ano_letivo=destino, turno=t.turno, defaults={"etapa": t.etapa, "vagas": t.vagas})
        criadas += novo
    messages.success(request, f"{criadas} turma(s) copiada(s) de {origem.ano} para {destino.ano}.")
    return redirect(f"/administracao/turmas/?ano={destino.pk}")


# ---------- usuários ----------
@superuser_required
def usuarios_list(request):
    usuarios = list(User.objects.order_by("-is_active", "first_name", "username"))
    for u in usuarios:
        u.perfil = {"admin": "Administrador", "secretaria": "Secretaria", "familia": "Família / professor"}[perfil_do_usuario(u)]
    return render(request, "administracao/usuarios.html", {"usuarios": usuarios})


@superuser_required
def usuario_form(request, pk=None):
    usuario = get_object_or_404(User, pk=pk) if pk else None
    form = UsuarioForm(request.POST or None, instance=usuario, editor=request.user)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        messages.success(request, f"Usuário {usuario.username} salvo.")
        return redirect("adm_usuarios")
    return _form_generico(
        request, form, "Editar usuário" if usuario else "Novo usuário", "adm_usuarios",
        "Para trocar a senha de um usuário existente, use “Redefinir senha” na lista." if usuario else
        "A pessoa entra com o usuário e a senha definidos aqui. Ela poderá pedir a troca à secretaria.")


@superuser_required
def usuario_senha(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    form = SenhaForm(request.POST or None, usuario=usuario)
    if request.method == "POST" and form.is_valid():
        usuario.set_password(form.cleaned_data["password1"])
        usuario.save(update_fields=["password"])
        messages.success(request, f"Senha de {usuario.username} redefinida.")
        return redirect("adm_usuarios")
    return _form_generico(request, form, f"Redefinir senha — {usuario.get_full_name() or usuario.username}", "adm_usuarios",
                          "A senha antiga deixa de valer imediatamente.")


@superuser_required
@require_POST
def usuario_ativo(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario.is_active:
        if usuario.pk == request.user.pk:
            messages.error(request, "Você não pode desativar o seu próprio acesso.")
        elif ultimo_administrador(usuario):
            messages.error(request, "Este é o único administrador ativo e não pode ser desativado.")
        else:
            usuario.is_active = False
            usuario.save(update_fields=["is_active"])
            messages.success(request, f"{usuario.username} foi desativado e não consegue mais entrar.")
    else:
        usuario.is_active = True
        usuario.save(update_fields=["is_active"])
        messages.success(request, f"{usuario.username} foi reativado.")
    return redirect("adm_usuarios")


# ---------- categorias de despesa ----------
@staff_required
def categorias_list(request):
    categorias = CategoriaDespesa.objects.annotate(n=Count("despesas"))
    return render(request, "administracao/categorias.html", {"categorias": categorias})


@staff_required
def categoria_form(request, pk=None):
    categoria = get_object_or_404(CategoriaDespesa, pk=pk) if pk else None
    form = CategoriaDespesaForm(request.POST or None, instance=categoria, initial=None if categoria else {"ativa": True})
    if request.method == "POST" and form.is_valid():
        categoria = form.save()
        messages.success(request, f"Categoria \"{categoria.nome}\" salva.")
        return redirect("adm_categorias")
    return _form_generico(request, form, "Editar categoria" if categoria else "Nova categoria de despesa", "adm_categorias",
                          "Ex.: Uniformes, Passeios, Manutenção do ar-condicionado.")


@staff_required
@require_POST
def categoria_ativa(request, pk):
    categoria = get_object_or_404(CategoriaDespesa, pk=pk)
    categoria.ativa = not categoria.ativa
    categoria.save(update_fields=["ativa"])
    messages.success(request, f"Categoria \"{categoria.nome}\" {'ativada' if categoria.ativa else 'desativada'}.")
    return redirect("adm_categorias")


@staff_required
@require_POST
def categoria_excluir(request, pk):
    categoria = get_object_or_404(CategoriaDespesa, pk=pk)
    try:
        categoria.delete()
        messages.success(request, f"Categoria \"{categoria.nome}\" excluída.")
    except ProtectedError:
        messages.error(request, "Esta categoria já foi usada em despesas. Desative-a em vez de excluir.")
    return redirect("adm_categorias")
