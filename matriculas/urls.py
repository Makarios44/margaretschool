from django.urls import path

from . import views

urlpatterns = [
    path("", views.matricula_list, name="matricula_list"),
    path("nova/", views.matricula_form, name="matricula_create"),
    path("rematriculas/", views.rematricula_list, name="rematricula_list"),
    path("<int:pk>/", views.matricula_detail, name="matricula_detail"),
    path("<int:pk>/editar/", views.matricula_form, name="matricula_update"),
    path("<int:pk>/documentos/", views.matricula_documentos, name="matricula_documentos"),
    path("<int:pk>/documentos/adicionar/", views.matricula_documento_adicionar, name="matricula_documento_adicionar"),
    path("<int:pk>/ficha/", views.matricula_ficha, name="matricula_ficha"),
    path("<int:pk>/contrato/", views.matricula_contrato, name="matricula_contrato"),
]
