from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.static import serve


def home(request):
    """Página principal pública: anúncios, novidades, próximos eventos, fotos e contato."""
    from administracao import configuracao
    from calendario.servicos import proximos_eventos
    from divulgacao.models import Album, Anuncio

    from .contato import links_contato

    vigentes = Anuncio.objects.vigentes()
    albuns = (Album.objects.filter(visibilidade=Album.Visibilidade.PUBLICO)
              .annotate(n_fotos=Count("fotos")).filter(n_fotos__gt=0)[:4])
    destaques = list(vigentes.filter(destaque=True)[:6])
    novidades = list(vigentes.filter(destaque=False)[:6])
    return render(request, "home.html", {
        "destaques": destaques,
        "novidades": novidades,
        # Só anúncios vigentes entram na conta: com algum no ar a apresentação encolhe e a arte some.
        "apresentacao_compacta": bool(destaques or novidades),
        "albuns": albuns,
        "eventos": proximos_eventos(4, interno=False),
        "contato": links_contato(configuracao.escola()),
    })


class EscolaLoginView(LoginView):
    """Login com o template da escola; quem já entrou vai direto ao painel."""

    template_name = "login.html"
    redirect_authenticated_user = True


@login_required
def dashboard(request):
    """Painel inicial após o login."""
    from calendario.servicos import proximos_eventos

    from pre_matriculas.models import SolicitacaoPreMatricula

    pendentes = 0
    if request.user.is_staff:
        pendentes = SolicitacaoPreMatricula.objects.filter(
            status__in=[SolicitacaoPreMatricula.Status.RECEBIDA, SolicitacaoPreMatricula.Status.EM_ANALISE]
        ).count()
    return render(request, "dashboard.html", {
        "proximos": proximos_eventos(6, interno=request.user.is_staff),
        "pre_pendentes": pendentes,
    })


# Pastas de MEDIA_ROOT que qualquer visitante pode abrir (banners da página inicial).
MIDIA_PUBLICA = ("anuncios/",)


def midia(request, caminho):
    """Entrega os uploads em desenvolvimento e em produção.

    Banners dos anúncios são públicos; fotos de alunos e comprovantes de despesa só para a equipe.
    """
    publico = caminho.startswith(MIDIA_PUBLICA)
    if not publico and not (request.user.is_authenticated and request.user.is_staff):
        raise Http404  # não confirma nem que o arquivo existe
    resposta = serve(request, caminho, document_root=settings.MEDIA_ROOT)  # já bloqueia "../"
    resposta["Cache-Control"] = "public, max-age=86400" if publico else "private, no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
