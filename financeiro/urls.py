from django.urls import path

from . import views

urlpatterns = [
    path("", views.financeiro_painel, name="financeiro_painel"),
    path("cobrancas/", views.cobranca_list, name="cobranca_list"),
    path("despesas/", views.despesa_list, name="despesa_list"),
    path("despesas/nova/", views.despesa_form, name="despesa_create"),
    path("despesas/<int:pk>/", views.despesa_detail, name="despesa_detail"),
    path("despesas/<int:pk>/editar/", views.despesa_form, name="despesa_update"),
    path("despesas/<int:pk>/excluir/", views.despesa_excluir, name="despesa_delete"),
    path("nova/", views.cobranca_form, name="cobranca_create"),
    path("relatorio/", views.relatorio_mensal, name="relatorio_mensal"),
    path("gerar/<int:matricula_pk>/", views.gerar_mensalidades, name="gerar_mensalidades"),
    path("<int:pk>/", views.cobranca_detail, name="cobranca_detail"),
    path("<int:pk>/editar/", views.cobranca_form, name="cobranca_update"),
    path("<int:pk>/receber/", views.cobranca_receber, name="cobranca_receber"),
    path("<int:pk>/cancelar/", views.cobranca_cancelar, name="cobranca_cancelar"),
    path("<int:pk>/estornar/", views.cobranca_estornar, name="cobranca_estornar"),
    path("<int:pk>/recibo/", views.cobranca_recibo, name="cobranca_recibo"),
]
