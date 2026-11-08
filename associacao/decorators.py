"""
Decoradores de permissão para o Sistema de Gestão de Associações.

Garante que apenas utilizadores com o tipo correto possam aceder
a determinadas views.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


def direcao_required(view_func):
    """
    Decorador que exige que o utilizador seja da Direção.

    Se o utilizador não estiver autenticado, redireciona para login.
    Se for um associado, redireciona para o dashboard do associado com mensagem de erro.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, inicie sessão para aceder a esta página.')
            return redirect('login')

        if not hasattr(request.user, 'tipo') or request.user.tipo != 'direcao':
            messages.error(request, 'Acesso restrito à Direção da associação.')
            return redirect('dashboard_associado')

        return view_func(request, *args, **kwargs)
    return _wrapped_view


def associado_required(view_func):
    """
    Decorador que exige que o utilizador seja um Associado.

    Se o utilizador não estiver autenticado, redireciona para login.
    Se for da Direção, redireciona para o dashboard da Direção com mensagem de erro.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, inicie sessão para aceder a esta página.')
            return redirect('login')

        if not hasattr(request.user, 'tipo') or request.user.tipo != 'associado':
            messages.error(request, 'Esta área é exclusiva para associados.')
            return redirect('dashboard_direcao')

        if getattr(request.user, 'exigir_alteracao_password', False) and request.resolver_match.url_name != 'definir_palavra_passe_associado':
            messages.info(request, 'Defina uma nova palavra-passe para continuar.')
            return redirect('definir_palavra_passe_associado')

        return view_func(request, *args, **kwargs)
    return _wrapped_view


def login_required_custom(view_func):
    """
    Decorador personalizado que redireciona para o dashboard correto após login.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Por favor, inicie sessão para aceder a esta página.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
