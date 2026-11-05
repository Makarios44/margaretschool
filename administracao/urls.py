from django.urls import path

from . import views

urlpatterns = [
    path("", views.hub, name="administracao"),
    path("escola/", views.escola_dados, name="adm_escola"),
    path("anos/", views.anos_list, name="adm_anos"),
    path("anos/novo/", views.ano_form, name="adm_ano_novo"),
    path("anos/<int:pk>/editar/", views.ano_form, name="adm_ano_editar"),
    path("anos/<int:pk>/excluir/", views.ano_excluir, name="adm_ano_excluir"),
    path("turmas/", views.turmas_list, name="adm_turmas"),
    path("turmas/nova/", views.turma_form, name="adm_turma_nova"),
    path("turmas/copiar/", views.turmas_copiar, name="adm_turmas_copiar"),
    path("turmas/<int:pk>/editar/", views.turma_form, name="adm_turma_editar"),
    path("turmas/<int:pk>/excluir/", views.turma_excluir, name="adm_turma_excluir"),
    path("categorias/", views.categorias_list, name="adm_categorias"),
    path("categorias/nova/", views.categoria_form, name="adm_categoria_nova"),
    path("categorias/<int:pk>/editar/", views.categoria_form, name="adm_categoria_editar"),
    path("categorias/<int:pk>/ativa/", views.categoria_ativa, name="adm_categoria_ativa"),
    path("categorias/<int:pk>/excluir/", views.categoria_excluir, name="adm_categoria_excluir"),
    path("usuarios/", views.usuarios_list, name="adm_usuarios"),
    path("usuarios/novo/", views.usuario_form, name="adm_usuario_novo"),
    path("usuarios/<int:pk>/editar/", views.usuario_form, name="adm_usuario_editar"),
    path("usuarios/<int:pk>/senha/", views.usuario_senha, name="adm_usuario_senha"),
    path("usuarios/<int:pk>/link-senha/", views.usuario_link, name="adm_usuario_link"),
    path("email/", views.email_status, name="adm_email"),
    path("usuarios/<int:pk>/ativo/", views.usuario_ativo, name="adm_usuario_ativo"),
]
