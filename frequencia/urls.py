from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="frequencia"),
    path("chamada/<int:turma_pk>/<str:data>/", views.chamada, name="frequencia_chamada"),
    path("chamada/<int:turma_pk>/<str:data>/excluir/", views.chamada_excluir, name="frequencia_chamada_excluir"),
    path("aluno/", views.consulta_aluno, name="frequencia_consulta_aluno"),
    path("aluno/<int:pk>/", views.frequencia_do_aluno, name="frequencia_aluno"),
    path("relatorio/", views.relatorio, name="frequencia_relatorio"),
]
