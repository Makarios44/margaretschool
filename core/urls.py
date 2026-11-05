from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy
from django.urls import path

from . import views
from .forms_senha import PedidoDeSenhaForm

urlpatterns = [
    path("", views.home, name="home"),
    path("entrar/", views.EscolaLoginView.as_view(), name="login"),
    path("sair/", LogoutView.as_view(), name="logout"),
    path("painel/", views.dashboard, name="dashboard"),
    path("ajuda/", views.ajuda, name="ajuda"),
    path("ajuda/concluir/", views.ajuda_concluir, name="ajuda_concluir"),
    path("senha/esqueci/", auth_views.PasswordResetView.as_view(
        template_name="registration/senha_pedido.html", form_class=PedidoDeSenhaForm,
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("senha/enviada/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/senha_enviada.html"), name="password_reset_done"),
    path("senha/nova/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/senha_nova.html",
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("senha/pronto/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/senha_pronto.html"), name="password_reset_complete"),
]
