from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("entrar/", views.EscolaLoginView.as_view(), name="login"),
    path("sair/", LogoutView.as_view(), name="logout"),
    path("painel/", views.dashboard, name="dashboard"),
]
