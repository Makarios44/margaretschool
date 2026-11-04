from django.urls import path

from . import views

urlpatterns = [
    path("", views.documento_list, name="documento_list"),
    path("emitir/", views.documento_emitir, name="documento_emitir"),
    path("emitir/<slug:slug>/<int:aluno_pk>/", views.documento_form, name="documento_form"),
    path("ficha/<int:aluno_pk>/", views.ficha_individual, name="ficha_individual"),
    path("ficha/<int:aluno_pk>/pdf/", views.ficha_individual_pdf, name="ficha_individual_pdf"),
    path("registros/<int:matricula_pk>/", views.registro_escolar, name="registro_escolar"),
    path("folha-de-ponto/", views.folha_ponto_form, name="folha_ponto_form"),
    path("folha-de-ponto/imprimir/", views.folha_ponto_imprimir, name="folha_ponto_imprimir"),
    path("folha-de-ponto/pdf/", views.folha_ponto_pdf, name="folha_ponto_pdf"),
    path("<int:pk>/", views.documento_ver, name="documento_ver"),
    path("<int:pk>/pdf/", views.documento_pdf, name="documento_pdf"),
    path("<int:pk>/anular/", views.documento_anular, name="documento_anular"),
]
