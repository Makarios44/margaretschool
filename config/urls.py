from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from pre_matriculas.views import formulario_publico

urlpatterns = [
    path("admin/", admin.site.urls),
    path("alunos/", include("alunos.urls")),
    path("matriculas/", include("matriculas.urls")),
    path("financeiro/", include("financeiro.urls")),
    path("documentos/", include("documentos.urls")),
    path("frequencia/", include("frequencia.urls")),
    path("calendario/", include("calendario.urls")),
    path("administracao/", include("administracao.urls")),
    path("", include("divulgacao.urls")),
    path("pre-matricula/<str:token>/", formulario_publico, name="pre_matricula_publica"),
    path("pre-matriculas/", include("pre_matriculas.urls")),
    path("", include("core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
