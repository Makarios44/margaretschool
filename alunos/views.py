from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.mixins import staff_required
from matriculas.models import AnoLetivo, Matricula, Turma

from .forms import AlunoForm, ContatoFormSet, ResponsavelFormSet
from .models import Aluno
from .utils import normalizar, resumo_aluno


@staff_required
def aluno_list(request):
    qs = Aluno.objects.prefetch_related(
        "matriculas__turma", "matriculas__ano_letivo"
    )
    q = request.GET.get("q", "").strip()
    ano_id = request.GET.get("ano", "")
    turma_id = request.GET.get("turma", "")
    sit = request.GET.get("situacao", "")

    if q:
        qs = qs.buscar(q)

    ano = AnoLetivo.objects.filter(pk=ano_id).first() if ano_id.isdigit() else None
    if sit == "sem":
        # sem matrícula em nenhum ano, ou sem matrícula no ano escolhido
        qs = qs.exclude(matriculas__ano_letivo=ano) if ano else qs.filter(matriculas__isnull=True)
    else:
        cond = {}
        if ano:
            cond["matriculas__ano_letivo"] = ano
        if turma_id.isdigit():
            cond["matriculas__turma_id"] = int(turma_id)
        if sit in Matricula.Situacao.values:
            cond["matriculas__situacao"] = sit
        if cond:
            qs = qs.filter(**cond).distinct()  # mesma matrícula atende a todas as condições

    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    for a in page:  # matrícula do ano filtrado, ou a mais recente
        a.mat = next(
            (m for m in a.matriculas.all() if not ano or m.ano_letivo_id == ano.pk), None
        )

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "alunos/aluno_list.html", {
        "page_obj": page,
        "anos": AnoLetivo.objects.all(),
        "turmas": Turma.objects.select_related("ano_letivo"),
        "situacoes": Matricula.Situacao.choices,
        "f": {"q": q, "ano": ano_id, "turma": turma_id, "situacao": sit},
        "qs": params.urlencode(),
    })


@staff_required
def aluno_detail(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return render(request, "alunos/aluno_detail.html", {
        "aluno": aluno,
        "matriculas": aluno.matriculas.select_related("turma", "ano_letivo"),
    })


@staff_required
def aluno_form(request, pk=None):
    aluno = get_object_or_404(Aluno, pk=pk) if pk else None
    data = request.POST or None
    form = AlunoForm(data, request.FILES or None, instance=aluno)
    resp = ResponsavelFormSet(data, instance=aluno, prefix="resp")
    cont = ContatoFormSet(data, instance=aluno, prefix="cont")

    if request.method == "POST":
        if all([form.is_valid(), resp.is_valid(), cont.is_valid()]):
            with transaction.atomic():
                aluno = form.save()
                resp.instance = cont.instance = aluno
                resp.save()
                cont.save()
            messages.success(request, f"Cadastro de {aluno.nome} salvo.")
            return redirect("aluno_detail", pk=aluno.pk)
        messages.error(request, "Revise os campos destacados e tente de novo.")

    return render(request, "alunos/aluno_form.html", {
        "aluno": aluno, "form": form, "resp": resp, "cont": cont,
    })


@staff_required
def aluno_buscar(request):
    """Sugestões de alunos enquanto a pessoa digita (usado nos campos de escolher aluno)."""
    q = request.GET.get("q", "").strip()
    if len(normalizar(q)) < 2:
        return JsonResponse({"resultados": [], "total": 0})
    qs = Aluno.objects.buscar(q).prefetch_related(
        "responsaveis", "matriculas__turma", "matriculas__ano_letivo").order_by("nome", "data_nascimento")
    total = qs.count()
    return JsonResponse({"resultados": [resumo_aluno(a) for a in qs[:10]], "total": total})
