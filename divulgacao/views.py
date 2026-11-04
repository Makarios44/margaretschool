import mimetypes
from datetime import date

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.mixins import staff_required

from .forms import AlbumForm, AnuncioForm
from .models import Album, Anuncio, Foto


# ===================== público =====================
def avisos(request):
    return render(request, "divulgacao/avisos.html", {"anuncios": Anuncio.objects.vigentes()})


def galeria(request):
    albuns = Album.visiveis_para(request.user).annotate(n_fotos=Count("fotos"))
    if not (request.user.is_authenticated and request.user.is_staff):
        albuns = albuns.filter(n_fotos__gt=0)
    pagina = Paginator(albuns, 12).get_page(request.GET.get("page"))
    return render(request, "divulgacao/galeria.html", {"page_obj": pagina})


def album_detail(request, pk):
    album = get_object_or_404(Album, pk=pk)
    if not album.visivel_para(request.user):
        if album.visibilidade == Album.Visibilidade.LOGADOS and not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        raise Http404  # rascunho: nem confirma que existe
    return render(request, "divulgacao/album.html", {"album": album, "fotos": album.fotos.all()})


def foto_arquivo(request, pk, tipo):
    """Entrega a imagem só para quem pode ver o álbum (os arquivos não ficam em pasta pública)."""
    if tipo not in ("grande", "mini"):
        raise Http404
    foto = get_object_or_404(Foto.objects.select_related("album"), pk=pk)
    if not foto.album.visivel_para(request.user):
        raise Http404
    campo = foto.miniatura if tipo == "mini" else foto.imagem
    try:
        resposta = FileResponse(campo.open("rb"), content_type=mimetypes.guess_type(campo.name)[0] or "image/jpeg")
    except (FileNotFoundError, ValueError):
        raise Http404
    publico = foto.album.visibilidade == Album.Visibilidade.PUBLICO
    resposta["Cache-Control"] = "public, max-age=86400" if publico else "private, max-age=3600"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


# ===================== equipe: anúncios =====================
@staff_required
def anuncio_list(request):
    return render(request, "divulgacao/anuncio_list.html", {
        "anuncios": Anuncio.objects.all(), "aba": "anuncios",
        "n_albuns": Album.objects.count(),
    })


@staff_required
def anuncio_form(request, pk=None):
    anuncio = get_object_or_404(Anuncio, pk=pk) if pk else None
    if request.method == "POST":
        form = AnuncioForm(request.POST, request.FILES, instance=anuncio)
        if form.is_valid():
            novo = anuncio is None
            anuncio = form.save(commit=False)
            if novo:
                anuncio.criado_por = request.user
            anuncio.save()
            messages.success(request, "Anúncio salvo." if not novo else "Anúncio criado.")
            return redirect("divulgacao")
    else:
        form = AnuncioForm(instance=anuncio, initial=None if anuncio else {"inicio": date.today()})
    return render(request, "divulgacao/anuncio_form.html", {"form": form, "anuncio": anuncio})


@staff_required
@require_POST
def anuncio_ativo(request, pk):
    anuncio = get_object_or_404(Anuncio, pk=pk)
    anuncio.ativo = not anuncio.ativo
    anuncio.save(update_fields=["ativo"])
    messages.success(request, f"Anúncio {'ativado' if anuncio.ativo else 'desativado'}.")
    return redirect("divulgacao")


@staff_required
@require_POST
def anuncio_excluir(request, pk):
    anuncio = get_object_or_404(Anuncio, pk=pk)
    titulo = anuncio.titulo
    anuncio.delete()
    messages.success(request, f"Anúncio “{titulo}” excluído.")
    return redirect("divulgacao")


# ===================== equipe: álbuns =====================
@staff_required
def album_list(request):
    return render(request, "divulgacao/album_list.html", {
        "albuns": Album.objects.annotate(n_fotos=Count("fotos")), "aba": "albuns",
    })


@staff_required
def album_form(request, pk=None):
    album = get_object_or_404(Album, pk=pk) if pk else None
    if request.method == "POST":
        form = AlbumForm(request.POST, request.FILES, instance=album)
        if form.is_valid():
            novo = album is None
            with transaction.atomic():
                album = form.save(commit=False)
                if novo:
                    album.criado_por = request.user
                album.save()
                if not novo:
                    _atualizar_fotos_existentes(request, album)
                proxima = (album.fotos.order_by("-ordem").values_list("ordem", flat=True).first() or 0) + 1
                for i, (grande, mini) in enumerate(form.cleaned_data["fotos"]):
                    Foto.objects.create(album=album, imagem=grande, miniatura=mini, ordem=proxima + i)
                album.refresh_from_db(fields=["capa"])  # a capa pode ter sido removida acima
                if album.capa_id is None:
                    primeira = album.fotos.first()
                    if primeira:
                        album.capa = primeira
                        album.save(update_fields=["capa"])
            messages.success(request, "Álbum salvo.")
            return redirect("album_update", pk=album.pk)
    else:
        form = AlbumForm(instance=album, initial=None if album else {"data_atividade": date.today()})
    return render(request, "divulgacao/album_form.html", {
        "form": form, "album": album, "fotos": album.fotos.all() if album else [],
    })


def _atualizar_fotos_existentes(request, album):
    """Legendas, remoção e foto de capa das fotos que já estão no álbum."""
    fotos = list(album.fotos.all())
    for foto in fotos:
        if request.POST.get(f"remover_{foto.pk}"):
            foto.delete()
            continue
        legenda = request.POST.get(f"legenda_{foto.pk}", foto.legenda).strip()[:200]
        if legenda != foto.legenda:
            foto.legenda = legenda
            foto.save(update_fields=["legenda"])
    capa = request.POST.get("capa", "")
    if capa.isdigit():
        escolhida = album.fotos.filter(pk=int(capa)).first()
        if escolhida:
            album.capa = escolhida
            album.save(update_fields=["capa"])


@staff_required
@require_POST
def album_excluir(request, pk):
    album = get_object_or_404(Album, pk=pk)
    titulo = album.titulo
    album.capa = None
    album.save(update_fields=["capa"])
    album.delete()
    messages.success(request, f"Álbum “{titulo}” e suas fotos foram excluídos.")
    return redirect("album_list")
