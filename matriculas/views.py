from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from alunos.models import Aluno
from alunos.utils import filtrar_por_nome
from core.mixins import staff_required

from .forms import MatriculaForm
from .models import AnoLetivo, DocumentoMatricula, Matricula, Turma, Turno


@staff_required
def matricula_list(request):
    qs = Matricula.objects.select_related("aluno", "turma", "ano_letivo").annotate(
        pendentes=Count("documentos", filter=Q(documentos__entregue=False))
    ).order_by("-ano_letivo__ano", "aluno__nome")
    if "ano" in request.GET:  # "" = todos os anos
        ano_id = request.GET["ano"]
    else:
        padrao = AnoLetivo.padrao()
        ano_id = str(padrao.pk) if padrao else ""
    q = request.GET.get("q", "").strip()
    turma_id = request.GET.get("turma", "")
    sit = request.GET.get("situacao", "")
    turno = request.GET.get("turno", "")

    if ano_id.isdigit():
        qs = qs.filter(ano_letivo_id=int(ano_id))
    if q:
        qs = filtrar_por_nome(qs, q, "aluno__nome_busca")
    if turma_id.isdigit():
        qs = qs.filter(turma_id=int(turma_id))
    if sit in Matricula.Situacao.values:
        qs = qs.filter(situacao=sit)
    if turno in Turno.values:
        qs = qs.filter(turno=turno)

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "matriculas/matricula_list.html", {
        "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")),
        "anos": AnoLetivo.objects.all(),
        "turmas": Turma.objects.select_related("ano_letivo"),
        "situacoes": Matricula.Situacao.choices,
        "turnos": Turno.choices,
        "f": {"q": q, "ano": ano_id, "turma": turma_id, "situacao": sit, "turno": turno},
        "qs": params.urlencode(),
    })


def _initial_from_get(request):
    """Preenche o formulário a partir de ?aluno=&ano=&tipo= (usado na rematrícula)."""
    initial = {}
    aluno = Aluno.objects.filter(pk=request.GET["aluno"]).first() if request.GET.get("aluno", "").isdigit() else None
    ano = AnoLetivo.objects.filter(pk=request.GET["ano"]).first() if request.GET.get("ano", "").isdigit() else None
    ano = ano or AnoLetivo.padrao()
    if ano:
        initial["ano_letivo"] = ano
    if aluno:
        initial["aluno"] = aluno
        anterior = aluno.matriculas.first()
        if request.GET.get("tipo") == Matricula.Tipo.REMATRICULA:
            initial["tipo"] = Matricula.Tipo.REMATRICULA
            if anterior:  # aproveita os valores combinados no ano anterior
                initial["mensalidade"] = anterior.mensalidade
                initial["dia_vencimento"] = anterior.dia_vencimento
                initial["desconto_percentual"] = anterior.desconto_percentual
                initial["desconto_motivo"] = anterior.desconto_motivo
    return initial


@staff_required
def matricula_form(request, pk=None):
    matricula = get_object_or_404(Matricula, pk=pk) if pk else None
    if request.method == "POST":
        form = MatriculaForm(request.POST, instance=matricula)
        if form.is_valid():
            matricula = form.save()
            messages.success(request, "Matrícula salva.")
            return redirect("matricula_detail", pk=matricula.pk)
    else:
        form = MatriculaForm(
            instance=matricula, initial=None if matricula else _initial_from_get(request)
        )
    return render(request, "matriculas/matricula_form.html", {
        "form": form, "matricula": matricula,
    })


def _matricula_completa(pk):
    return get_object_or_404(
        Matricula.objects.select_related("aluno", "turma", "ano_letivo")
        .prefetch_related("documentos", "aluno__responsaveis", "aluno__contatos_emergencia"),
        pk=pk,
    )


@staff_required
def matricula_detail(request, pk):
    m = _matricula_completa(pk)
    existentes = set(m.documentos.values_list("tipo", flat=True))
    return render(request, "matriculas/matricula_detail.html", {
        "m": m, "cobrancas": m.cobrancas.all(),
        "docs_faltando": [(v, l) for v, l in DocumentoMatricula.Tipo.choices if v not in existentes],
    })


@staff_required
@require_POST
def matricula_documento_adicionar(request, pk):
    matricula = get_object_or_404(Matricula, pk=pk)
    tipo = request.POST.get("tipo", "")
    if tipo in DocumentoMatricula.Tipo.values:
        _, novo = DocumentoMatricula.objects.get_or_create(matricula=matricula, tipo=tipo)
        messages.success(request, "Documento acrescentado à lista." if novo else "Este documento já está na lista.")
    return redirect("matricula_detail", pk=pk)


@staff_required
@require_POST
def matricula_documentos(request, pk):
    matricula = get_object_or_404(Matricula, pk=pk)
    marcados = {int(v) for v in request.POST.getlist("entregue") if v.isdigit()}
    for doc in matricula.documentos.all():
        entregue = doc.pk in marcados
        if entregue != doc.entregue:
            doc.entregue = entregue
            doc.data_entrega = date.today() if entregue else None
            doc.save(update_fields=["entregue", "data_entrega"])
    messages.success(request, "Documentos atualizados.")
    return redirect("matricula_detail", pk=pk)


@staff_required
def matricula_ficha(request, pk):
    return render(request, "matriculas/ficha.html", {"m": _matricula_completa(pk)})


@staff_required
def matricula_contrato(request, pk):
    return render(request, "matriculas/contrato.html", {"m": _matricula_completa(pk), "hoje": date.today()})


@staff_required
def rematricula_list(request):
    """Alunos ativos no ano anterior que ainda não têm matrícula no ano escolhido."""
    anos = AnoLetivo.objects.all()
    destino = None
    if request.GET.get("ano", "").isdigit():
        destino = anos.filter(pk=request.GET["ano"]).first()
    destino = destino or AnoLetivo.padrao()
    anterior = anos.filter(ano__lt=destino.ano).first() if destino else None

    candidatos, ja_feitas = [], 0
    if destino and anterior:
        candidatos = (
            Aluno.objects.filter(
                matriculas__ano_letivo=anterior,
                matriculas__situacao=Matricula.Situacao.ATIVO,
            )
            .exclude(matriculas__ano_letivo=destino)
            .distinct()
            .prefetch_related(Prefetch(
                "matriculas",
                queryset=Matricula.objects.filter(ano_letivo=anterior).select_related("turma"),
                to_attr="mat_anterior",
            ))
        )
        ja_feitas = Matricula.objects.filter(
            ano_letivo=destino, tipo=Matricula.Tipo.REMATRICULA
        ).count()
    return render(request, "matriculas/rematricula_list.html", {
        "anos": anos, "destino": destino, "anterior": anterior,
        "candidatos": candidatos, "ja_feitas": ja_feitas,
    })
