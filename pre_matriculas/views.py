from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from alunos.models import Aluno, ContatoEmergencia, Responsavel
from alunos.utils import normalizar
from core.mixins import staff_required
from financeiro.models import Cobranca
from matriculas.models import AnoLetivo, Matricula

from .forms import AprovarPreMatriculaForm, SolicitacaoPreMatriculaForm
from .models import LinkPreMatricula, SolicitacaoPreMatricula

Status = SolicitacaoPreMatricula.Status


def _url_publica(request, link):
    return request.build_absolute_uri(reverse("pre_matricula_publica", args=[link.token]))


# ---------- links (equipe) ----------
@staff_required
def criar_link(request):
    if request.method == "POST":
        ano = get_object_or_404(AnoLetivo, pk=request.POST.get("ano_letivo"))
        link = LinkPreMatricula.objects.create(
            ano_letivo=ano,
            criado_por=request.user,
            expira_em=timezone.now() + timedelta(days=14),
            observacoes_internas=request.POST.get("observacoes_internas", "")[:250],
        )
        return render(request, "pre_matriculas/link_criado.html", {"link": link, "url": _url_publica(request, link)})
    return render(request, "pre_matriculas/criar_link.html", {"anos": AnoLetivo.objects.order_by("-ano")})


@staff_required
def lista_links(request):
    """Links gerados: dá para copiar de novo os que aguardam a família e desativar enviados por engano."""
    pagina = Paginator(LinkPreMatricula.objects.select_related("ano_letivo", "criado_por"), 25).get_page(
        request.GET.get("page"))
    for link in pagina:
        link.url = _url_publica(request, link) if link.valido else ""
    return render(request, "pre_matriculas/links.html", {"page_obj": pagina})


@staff_required
@require_POST
def desativar_link(request, pk):
    link = get_object_or_404(LinkPreMatricula, pk=pk)
    if link.valido:
        link.ativo = False
        link.save(update_fields=["ativo"])
        messages.success(request, "Link desativado: a família não conseguirá mais usá-lo.")
    else:
        messages.error(request, "Este link já não está mais disponível.")
    return redirect("pre_matricula_links")


# ---------- formulário público (família) ----------
@require_http_methods(["GET", "POST"])
def formulario_publico(request, token):
    link = get_object_or_404(LinkPreMatricula.objects.select_related("ano_letivo"), token=token)
    if not link.valido:
        return render(request, "pre_matriculas/link_indisponivel.html", status=410)
    if request.method == "POST":
        form = SolicitacaoPreMatriculaForm(request.POST, ano_letivo=link.ano_letivo)
        if form.is_valid():
            try:
                with transaction.atomic():
                    link = LinkPreMatricula.objects.select_for_update().get(pk=link.pk)
                    if not link.valido:
                        return render(request, "pre_matriculas/link_indisponivel.html", status=410)
                    solicitacao = form.save(commit=False)
                    solicitacao.link = link
                    solicitacao.save()
                    link.usado_em = timezone.now()
                    link.save(update_fields=["usado_em"])
            except IntegrityError:  # duas pessoas enviaram ao mesmo tempo com o mesmo link
                return render(request, "pre_matriculas/link_indisponivel.html", status=410)
            return render(request, "pre_matriculas/enviado.html", {"solicitacao": solicitacao})
    else:
        form = SolicitacaoPreMatriculaForm(ano_letivo=link.ano_letivo)
    return render(request, "pre_matriculas/formulario.html", {"form": form, "link": link})


# ---------- análise (equipe) ----------
@staff_required
def lista_solicitacoes(request):
    qs = SolicitacaoPreMatricula.objects.select_related("link__ano_letivo", "turma_desejada")
    status = request.GET.get("status", "")
    if status in Status.values:
        qs = qs.filter(status=status)
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "pre_matriculas/lista.html", {
        "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")),
        "status_atual": status, "status_choices": Status.choices, "qs": params.urlencode(),
    })


def _aluno_existente(s):
    return Aluno.objects.filter(nome_busca=normalizar(s.nome_crianca), data_nascimento=s.data_nascimento).first()


def _efetivar(solicitacao, d, existente):
    """Cria (numa transação) aluno, responsável, contato, matrícula e a cobrança da taxa."""
    ano = solicitacao.link.ano_letivo
    if existente:
        aluno = existente
    else:
        aluno = Aluno.objects.create(
            nome=solicitacao.nome_crianca, data_nascimento=solicitacao.data_nascimento,
            sexo=solicitacao.sexo, naturalidade=solicitacao.naturalidade,
            certidao_nascimento=solicitacao.certidao_nascimento, endereco=solicitacao.endereco,
            bairro=solicitacao.bairro, cidade=solicitacao.cidade, alergias=solicitacao.alergias,
            observacoes_cuidado=solicitacao.observacoes_cuidado,
        )
        Responsavel.objects.create(
            aluno=aluno, nome=solicitacao.nome_responsavel, parentesco=solicitacao.parentesco,
            cpf=solicitacao.cpf_responsavel, telefone=solicitacao.telefone, email=solicitacao.email,
            profissao=solicitacao.profissao, responsavel_legal=solicitacao.responsavel_legal,
            responsavel_financeiro=solicitacao.responsavel_financeiro,
        )
        if solicitacao.contato_emergencia_nome:
            ContatoEmergencia.objects.create(
                aluno=aluno, nome=solicitacao.contato_emergencia_nome,
                parentesco=solicitacao.contato_emergencia_parentesco,
                telefone=solicitacao.contato_emergencia_telefone,
                autorizado_buscar=solicitacao.contato_pode_buscar,
            )
    matricula = Matricula.objects.create(
        aluno=aluno, ano_letivo=ano, turma=d["turma"], tipo=d["tipo"], data_matricula=date.today(),
        situacao=Matricula.Situacao.ATIVO, taxa_matricula=d["taxa_matricula"], taxa_paga=False,
        mensalidade=d["mensalidade"], dia_vencimento=d["dia_vencimento"],
        observacoes=f"Criada a partir da pré-matrícula #{solicitacao.pk}.",
    )
    if d["taxa_matricula"] > Decimal("0.00"):
        Cobranca.objects.create(
            matricula=matricula, tipo=Cobranca.Tipo.TAXA_MATRICULA, descricao="Taxa de matrícula",
            vencimento=date.today(), valor=d["taxa_matricula"],
            observacoes="Cobrança criada após aprovação de pré-matrícula online.",
        )
    solicitacao.status = Status.APROVADA
    solicitacao.aluno_criado = aluno
    solicitacao.matricula_criada = matricula
    solicitacao.save(update_fields=["status", "aluno_criado", "matricula_criada", "observacoes_secretaria"])
    return matricula


@staff_required
@require_http_methods(["GET", "POST"])
def analisar_solicitacao(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoPreMatricula.objects.select_related(
            "link__ano_letivo", "turma_desejada", "aluno_criado", "matricula_criada"), pk=pk)
    ano = solicitacao.link.ano_letivo

    if solicitacao.status == Status.APROVADA:  # só leitura, com atalhos para o que foi criado
        return render(request, "pre_matriculas/analisar.html", {"solicitacao": solicitacao, "somente_leitura": True})

    acao = request.POST.get("acao") if request.method == "POST" else None
    if acao == "em_analise":
        if solicitacao.status == Status.RECEBIDA:
            solicitacao.status = Status.EM_ANALISE
            solicitacao.save(update_fields=["status"])
            messages.success(request, "Solicitação marcada como em análise.")
        return redirect("pre_matricula_analisar", pk=pk)
    if acao == "rejeitar":
        solicitacao.status = Status.REJEITADA
        solicitacao.observacoes_secretaria = request.POST.get("observacoes_secretaria", "")
        solicitacao.save(update_fields=["status", "observacoes_secretaria"])
        messages.success(request, "Solicitação marcada como rejeitada.")
        return redirect("pre_matricula_lista")

    existente = _aluno_existente(solicitacao)
    if request.method == "POST":
        form = AprovarPreMatriculaForm(request.POST, ano_letivo=ano)
        if form.is_valid():
            d = form.cleaned_data
            turma = d["turma"]
            if turma.ano_letivo_id != ano.pk:
                form.add_error("turma", "A turma deve pertencer ao ano letivo do link.")
            elif turma.vagas is not None and turma.ocupacao >= turma.vagas:
                form.add_error("turma", "Esta turma não possui vagas disponíveis.")
            elif existente and not d["usar_aluno_existente"]:
                form.add_error(None, f"Já existe um aluno com este nome e data de nascimento ({existente.nome}). "
                                     "Marque \"Usar o cadastro existente\" para só criar a matrícula, "
                                     "ou rejeite a solicitação se for outra criança.")
            elif existente and existente.matriculas.filter(ano_letivo=ano).exists():
                form.add_error(None, f"{existente.nome} já tem matrícula em {ano.ano}.")
            else:
                solicitacao.observacoes_secretaria = request.POST.get("observacoes_secretaria", "")
                try:
                    with transaction.atomic():
                        matricula = _efetivar(solicitacao, d, existente if d["usar_aluno_existente"] else None)
                except IntegrityError:
                    form.add_error(None, "Não foi possível concluir porque algum dado já existe. Recarregue a página.")
                else:
                    messages.success(
                        request, "Pré-matrícula aprovada: aluno e matrícula criados. "
                                 "Falta gerar as mensalidades na seção Financeiro desta matrícula.")
                    return redirect("matricula_detail", pk=matricula.pk)
    else:
        form = AprovarPreMatriculaForm(
            ano_letivo=ano,
            initial={"turma": solicitacao.turma_desejada, "mensalidade": "0.00", "taxa_matricula": "0.00"},
        )
    return render(request, "pre_matriculas/analisar.html", {
        "solicitacao": solicitacao, "form": form, "existente": existente, "somente_leitura": False,
    })
