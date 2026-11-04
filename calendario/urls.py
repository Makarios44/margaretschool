from django.urls import path

from . import views

urlpatterns = [
    # público (somente leitura; eventos internos só aparecem para a equipe)
    path("", views.calendario_mes, name="calendario"),
    path("<int:ano>/<int:mes>/", views.calendario_mes, name="calendario_mes"),
    path("ano/<int:ano>/", views.calendario_ano, name="calendario_ano"),
    path("agenda/", views.calendario_agenda, name="calendario_agenda"),
    path("evento/<int:pk>/", views.evento_detail, name="evento_detail"),
    path("calendario.ics", views.calendario_ics, name="calendario_ics"),
    path("imprimir/<int:ano>/", views.calendario_imprimir, name="calendario_imprimir"),
    # equipe
    path("imprimir/<int:ano>/pdf/", views.calendario_pdf, name="calendario_pdf"),
    path("eventos/", views.evento_list, name="evento_list"),
    path("eventos/novo/", views.evento_form, name="evento_create"),
    path("eventos/<int:pk>/editar/", views.evento_form, name="evento_update"),
    path("eventos/<int:pk>/excluir/", views.evento_excluir, name="evento_delete"),
    path("feriados/", views.feriados_gerar, name="feriados_gerar"),
    path("anos/<int:pk>/", views.ano_configurar, name="ano_configurar"),
    path("dias-letivos/", views.dias_letivos_view, name="dias_letivos"),
]
