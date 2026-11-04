from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista_solicitacoes, name="pre_matricula_lista"),
    path("novo-link/", views.criar_link, name="pre_matricula_criar_link"),
    path("links/", views.lista_links, name="pre_matricula_links"),
    path("links/<int:pk>/desativar/", views.desativar_link, name="pre_matricula_desativar_link"),
    path("<int:pk>/", views.analisar_solicitacao, name="pre_matricula_analisar"),
]
