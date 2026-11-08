"""
Views de autenticação: login, logout, redirecionamento pós-login.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import connection

from . import mongodb


def _password_submetida(post, login_type):
    """Lê a palavra-passe do painel ativo.

    O formulário tem dois campos no mesmo pedido. O painel ativo envia
    password_associado ou password_associacao. Pedidos antigos enviam
    password; se vierem os dois, o primeiro é o do associado.
    """
    campo = 'password_associacao' if login_type == 'associacao' else 'password_associado'
    if campo in post:
        return post.get(campo, '')
    valores = post.getlist('password')
    if not valores:
        return ''
    return valores[-1] if login_type == 'associacao' else valores[0]


def login_view(request):
    """
    Página de login única para Direção e Associados.

    O backend de autenticação tenta primeiro DirecaoBackend,
    depois AssociadoBackend (definido em AUTHENTICATION_BACKENDS).
    """
    if request.user.is_authenticated:
        return redirect_pos_login(request.user)

    errors = {}

    if request.method == 'POST':
        login_type = request.POST.get('login_type', 'associado')

        # Validar campos individualmente por tipo de login
        if login_type == 'associado':
            nif = request.POST.get('nif', request.POST.get('nipc', '')).strip()
            associacao_nipc = request.POST.get('associacao_nipc', '').strip()
            password = _password_submetida(request.POST, login_type)

            if not nif or not password:
                errors['auth'] = 'Por favor, preencha NIF e palavra-passe'
            else:
                nipc = nif
        else:  # associacao
            nipc = request.POST.get('nipc', '').strip()
            password = _password_submetida(request.POST, login_type)

            if not nipc or not password:
                errors['auth'] = 'Por favor, preencha NIPC e palavra-passe'

        # Se não há erros de validação, tentar autenticar
        if not errors:
            from django.contrib.auth import authenticate
            user = authenticate(
                request,
                username=nipc,
                password=password,
                association_nipc=associacao_nipc if login_type == 'associado' else None,
            )

            if user is not None:
                auth_login(request, user)
                messages.success(request, f'Bem-vindo, {user.get_short_name()}!')

                # Log login to MongoDB
                user_type = getattr(user, 'tipo', 'unknown')
                user_id = (
                    getattr(user, 'id_associado', None) if user_type == 'associado'
                    else getattr(user, 'id_associacao', None)
                )
                mongodb.log_audit(
                    action='login',
                    entity_type='auth',
                    user_id=user_id,
                    user_type=user_type,
                    details={'tipo_login': login_type},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    success=True,
                    association_id=getattr(user, 'id_associacao', None),
                )

                # Log user activity
                mongodb.log_user_activity(
                    user_id=user_id,
                    user_type=user_type,
                    action='login',
                    session_id=request.session.session_key,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )

                return redirect_pos_login(user)
            else:
                # Associate failed attempts with an association only when the
                # user supplied its NIPC; never persist the submitted NIF/NIPC.
                nipc_contexto = associacao_nipc if login_type == 'associado' else nipc
                association_id_context = None
                if nipc_contexto:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT id_associacao FROM associacao WHERE nipc = %s', [nipc_contexto])
                        association_row = cursor.fetchone()
                        association_id_context = association_row[0] if association_row else None

                mongodb.log_audit(
                    action='login_failed',
                    entity_type='auth',
                    user_id=None,
                    user_type='unknown',
                    details={'tipo_login': login_type},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    success=False,
                    error_message='Invalid credentials',
                    association_id=association_id_context,
                )
                errors['auth'] = (
                    'Credenciais inválidas'
                    if login_type == 'associado'
                    else 'NIPC ou palavra-passe inválidos'
                )

    return render(request, 'associacao/login.html', {'errors': errors, 'login_type': request.POST.get('login_type', request.GET.get('login_type', 'associado'))})


def logout_view(request):
    """Logout e redirecionamento para login."""
    user_name = request.user.get_short_name() if request.user.is_authenticated else ''
    user_type = getattr(request.user, 'tipo', 'unknown') if request.user.is_authenticated else 'unknown'
    user_id = None
    if request.user.is_authenticated:
        user_id = (
            getattr(request.user, 'id_associado', None) if user_type == 'associado'
            else getattr(request.user, 'id_associacao', None)
        )

    # Log logout to MongoDB
    if user_id:
        mongodb.log_audit(
            action='logout',
            entity_type='auth',
            user_id=user_id,
            user_type=user_type,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            success=True,
            association_id=getattr(request.user, 'id_associacao', None),
        )

        mongodb.log_user_activity(
            user_id=user_id,
            user_type=user_type,
            action='logout',
            session_id=request.session.session_key,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

    auth_logout(request)
    if user_name:
        messages.info(request, f'Até breve, {user_name}!')
    else:
        messages.info(request, 'Sessão terminada com sucesso.')
    return redirect('login')


def redirect_pos_login(user):
    """
    Redireciona para o dashboard apropriado conforme o tipo de utilizador.
    """
    if hasattr(user, 'tipo'):
        if user.tipo == 'direcao':
            return redirect('dashboard_direcao')
        elif user.tipo == 'associado':
            if getattr(user, 'exigir_alteracao_password', False):
                return redirect('definir_palavra_passe_associado')
            return redirect('dashboard_associado')

    # Fallback (não deveria acontecer)
    # Can't use messages here since we don't have request
    return redirect('login')


# Alias para compatibilidade com urls
login = login_view
logout = logout_view
