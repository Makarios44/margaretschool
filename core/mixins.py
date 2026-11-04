from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """Exige login e que o usuário seja da equipe (secretaria/direção).

    Quem está logado mas não é da equipe recebe 403, para não entrar em
    loop de redirecionamento com a tela de login.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return login_required(wrapper)


def superuser_required(view):
    """Só administradores (superusuário). Quem está logado mas não é administrador recebe 403."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return login_required(wrapper)
