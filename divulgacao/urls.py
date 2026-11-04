from django.urls import path

from . import views

urlpatterns = [
    # público
    path("avisos/", views.avisos, name="avisos"),
    path("galeria/", views.galeria, name="galeria"),
    path("galeria/<int:pk>/", views.album_detail, name="album_detail"),
    path("galeria/foto/<int:pk>/<str:tipo>/", views.foto_arquivo, name="foto_arquivo"),
    # equipe
    path("divulgacao/", views.anuncio_list, name="divulgacao"),
    path("divulgacao/anuncios/novo/", views.anuncio_form, name="anuncio_create"),
    path("divulgacao/anuncios/<int:pk>/editar/", views.anuncio_form, name="anuncio_update"),
    path("divulgacao/anuncios/<int:pk>/ativo/", views.anuncio_ativo, name="anuncio_ativo"),
    path("divulgacao/anuncios/<int:pk>/excluir/", views.anuncio_excluir, name="anuncio_delete"),
    path("divulgacao/albuns/", views.album_list, name="album_list"),
    path("divulgacao/albuns/novo/", views.album_form, name="album_create"),
    path("divulgacao/albuns/<int:pk>/editar/", views.album_form, name="album_update"),
    path("divulgacao/albuns/<int:pk>/excluir/", views.album_excluir, name="album_delete"),
]
