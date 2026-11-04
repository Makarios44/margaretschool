from django.urls import path

from . import views

urlpatterns = [
    path("", views.aluno_list, name="aluno_list"),
    path("novo/", views.aluno_form, name="aluno_create"),
    path("buscar/", views.aluno_buscar, name="aluno_buscar"),
    path("<int:pk>/", views.aluno_detail, name="aluno_detail"),
    path("<int:pk>/editar/", views.aluno_form, name="aluno_update"),
]
