from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_GET
from django.utils import timezone
from datetime import date, datetime, time
from datetime import timezone as datetime_timezone
import secrets

from . import database
from . import mongodb
from .forms import (
    MandatoForm,
    ExercicioCargoForm,
    AssociacaoForm,
    EventoForm,
    AssociadoForm,
    QuotaForm,
    OrgaoSocialForm,
    CargoForm,
    MovimentoBancarioForm,
    PagamentoForm,
    TipoDocumentoForm,
    DocumentoForm,
    ImportarCSVForm,
    ConciliarForm,
    DesfazerConciliacaoForm,
    FiltroMovimentosForm
    , AlterarPalavraPasseForm, PassagemPosseForm, DefinirPalavraPasseAssociadoForm, PerfilAssociadoForm
)
from .decorators import direcao_required, associado_required


def registar_auditoria(request, action, entity_type, entity_id=None, details=None):
    """Regista a ação com o ator e o contexto da associação autenticada."""
    user = request.user
    user_type = getattr(user, 'tipo', 'unknown')
    user_id = (
        getattr(user, 'id_associado', None) if user_type == 'associado'
        else getattr(user, 'id_associacao', None) if user_type == 'direcao'
        else getattr(user, 'id', None)
    )
    return mongodb.log_audit(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        user_type=user_type,
        details=details or {},
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT'),
        association_id=getattr(user, 'id_associacao', None),
    )


@require_GET
def localidade_por_codigo_postal(request):
    """
    Endpoint AJAX para obter a localidade a partir do código postal.
    """
    codigo_postal = request.GET.get('codigo_postal', '').strip()

    if not codigo_postal:
        return JsonResponse({'success': False, 'error': 'Código postal não fornecido'})

    # Validar formato básico (4 dígitos + "-" + 3 dígitos)
    import re
    if not re.match(r'^\d{4}-\d{3}$', codigo_postal):
        return JsonResponse({'success': False, 'error': 'Formato inválido. Use 0000-000'})

    localidade = database.obter_localidade_por_codigo_postal(codigo_postal)

    if localidade:
        return JsonResponse({
            'success': True,
            'id_localidade': localidade[0],
            'nome_localidade': localidade[1]
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Código postal não encontrado na base de dados'
        })


@direcao_required
def registar_mandato(request):
    if request.method == 'POST':
        form = MandatoForm(request.POST)

        if form.is_valid():
            if database.mandato_sobrepoe(form.cleaned_data['data_inicio'], form.cleaned_data['data_fim'], request.user.id_associacao):
                form.add_error(None, 'O mandato sobrepõe-se a um mandato já registado.')
                return render(request, 'associacao/registar_mandato.html', {'form': form})
            try:
                database.inserir_mandato(
                    form.cleaned_data['data_inicio'],
                    form.cleaned_data['data_fim'],
                    request.user.id_associacao
                )
            except Exception as error:
                form.add_error(None, str(error))
                return render(request, 'associacao/registar_mandato.html', {'form': form})

            # Log to MongoDB
            mongodb.log_audit(
                action='create',
                entity_type='mandato',
                user_id=request.user.id_associacao,
                user_type='direcao',
                details={
                    'data_inicio': str(form.cleaned_data['data_inicio']),
                    'data_fim': str(form.cleaned_data['data_fim']) if form.cleaned_data['data_fim'] else None,
                    'id_associacao': request.user.id_associacao
                },
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT'),
                association_id=request.user.id_associacao,
            )

            messages.success(request, 'Mandato registado com sucesso.')
            return redirect('listar_mandatos')

    else:
        form = MandatoForm()

    return render(
        request,
        'associacao/registar_mandato.html',
        {'form': form}
    )


@direcao_required
def listar_mandatos(request):
    mandatos = database.listar_mandatos(request.user.id_associacao)
    hoje = date.today()
    mandatos = [
        (*mandato, mandato[1] <= hoje and (mandato[2] is None or mandato[2] >= hoje))
        for mandato in mandatos
    ]

    return render(
        request,
        'associacao/listar_mandatos.html',
        {
            'mandatos': mandatos,
            'mandatos_ativos': sum(1 for mandato in mandatos if mandato[4]),
            'mandatos_encerrados': sum(1 for mandato in mandatos if mandato[2] and mandato[2] < hoje),
        }
    )


@direcao_required
def detalhe_mandato(request, id_mandato):
    mandato = database.obter_mandato(id_mandato)
    if not mandato or mandato[3] != request.user.id_associacao:
        raise Http404('Mandato não encontrado.')
    return render(request, 'associacao/detalhe_mandato.html', {
        'mandato': mandato,
        'composicao': database.obter_composicao_mandato(id_mandato, request.user.id_associacao),
    })


@direcao_required
def alterar_palavra_passe(request):
    if request.method == 'POST':
        form = AlterarPalavraPasseForm(request.POST)
        if form.is_valid():
            from django.contrib.auth.hashers import check_password
            with connection.cursor() as cursor:
                cursor.execute('SELECT password_hash FROM associacao WHERE id_associacao = %s', [request.user.id_associacao])
                password_hash = cursor.fetchone()[0]
            if not check_password(form.cleaned_data['palavra_passe_atual'], password_hash):
                form.add_error('palavra_passe_atual', 'A palavra-passe atual está incorreta.')
            else:
                with connection.cursor() as cursor:
                    cursor.execute('UPDATE associacao SET password_hash = %s WHERE id_associacao = %s', [
                        make_password(form.cleaned_data['nova_palavra_passe']), request.user.id_associacao,
                    ])
                registar_auditoria(request, 'credentials_changed', 'associacao')
                from django.contrib.auth import logout
                logout(request)
                messages.success(request, 'Palavra-passe alterada. Inicie sessão novamente.')
                return redirect('login')
    else:
        form = AlterarPalavraPasseForm()
    return render(request, 'associacao/alterar_palavra_passe.html', {'form': form})


@associado_required
def definir_palavra_passe_associado(request):
    if request.method == 'POST':
        form = DefinirPalavraPasseAssociadoForm(request.POST)
        if form.is_valid():
            password_hash = make_password(form.cleaned_data['nova_palavra_passe'])
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE associado
                       SET password_hash = %s, exigir_alteracao_password = FALSE
                       WHERE id_associado = %s AND id_associacao = %s""",
                    [password_hash, request.user.id_associado, request.user.id_associacao],
                )
            request.user.password_hash = password_hash
            request.user.exigir_alteracao_password = False
            update_session_auth_hash(request, request.user)
            registar_auditoria(request, 'credentials_changed', 'associado', request.user.id_associado, {
                'alteracao': 'primeiro_acesso',
            })
            messages.success(request, 'Palavra-passe definida com sucesso.')
            return redirect('dashboard_associado')
    else:
        form = DefinirPalavraPasseAssociadoForm()
    return render(request, 'associacao/definir_palavra_passe_associado.html', {'form': form})


@direcao_required
def passagem_posse(request):
    if request.method == 'POST':
        form = PassagemPosseForm(request.POST, id_associacao=request.user.id_associacao)
        if form.is_valid():
            import secrets
            nova_palavra_passe = secrets.token_urlsafe(16)
            try:
                database.passagem_posse(
                    int(form.cleaned_data['id_mandato_anterior']), form.cleaned_data['data_inicio'],
                    form.cleaned_data['data_fim'], int(form.cleaned_data['id_presidente']),
                    form.composicao(), make_password(nova_palavra_passe), request.user.id_associacao,
                )
            except Exception as error:
                form.add_error(None, str(error))
            else:
                registar_auditoria(request, 'handover', 'mandato', details={
                    'id_mandato_anterior': int(form.cleaned_data['id_mandato_anterior']),
                    'id_presidente': int(form.cleaned_data['id_presidente']),
                })
                from django.contrib.auth import logout
                logout(request)
                messages.success(request, f'Passagem de posse concluída. Nova palavra-passe administrativa: {nova_palavra_passe}')
                return redirect('login')
    else:
        form = PassagemPosseForm(id_associacao=request.user.id_associacao)
    return render(request, 'associacao/passagem_posse.html', {'form': form})


@direcao_required
def registar_exercicio_cargo(request):
    if request.method == 'POST':
        form = ExercicioCargoForm(request.POST, id_associacao=request.user.id_associacao)

        if form.is_valid():
            # Validar que associado, cargo e mandato pertencem à mesma associação
            id_associado = int(form.cleaned_data['id_associado'])
            id_cargo = int(form.cleaned_data['id_cargo'])
            id_mandato = int(form.cleaned_data['id_mandato'])
            
            # Verificar associação do associado
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT id_associacao FROM associado WHERE id_associado = %s", [id_associado])
                associado_row = cursor.fetchone()
                if not associado_row or associado_row[0] != request.user.id_associacao:
                    form.add_error('id_associado', 'Associado não pertence a esta associação.')
                    return render(request, 'associacao/registar_exercicio_cargo.html', {'form': form})
                
                # Verificar associação do cargo (via orgao_social)
                cursor.execute("""
                    SELECT os.id_associacao 
                    FROM cargo c
                    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
                    WHERE c.id_cargo = %s
                """, [id_cargo])
                cargo_row = cursor.fetchone()
                if not cargo_row or cargo_row[0] != request.user.id_associacao:
                    form.add_error('id_cargo', 'Cargo não pertence a esta associação.')
                    return render(request, 'associacao/registar_exercicio_cargo.html', {'form': form})
                
                # Verificar associação do mandato
                cursor.execute("SELECT id_associacao FROM mandato WHERE id_mandato = %s", [id_mandato])
                mandato_row = cursor.fetchone()
                if not mandato_row or mandato_row[0] != request.user.id_associacao:
                    form.add_error('id_mandato', 'Mandato não pertence a esta associação.')
                    return render(request, 'associacao/registar_exercicio_cargo.html', {'form': form})

            database.inserir_exercicio_cargo(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                id_associado,
                id_cargo,
                id_mandato,
                request.user.id_associacao
            )
            registar_auditoria(request, 'create', 'exercicio_cargo', details={'id_associado': id_associado, 'id_cargo': id_cargo, 'id_mandato': id_mandato})

            messages.success(request, 'Exercício de cargo registado com sucesso.')
            return redirect('listar_exercicios_cargo')

    else:
        form = ExercicioCargoForm(id_associacao=request.user.id_associacao)

    return render(
        request,
        'associacao/registar_exercicio_cargo.html',
        {'form': form}
    )


@direcao_required
def listar_exercicios_cargo(request):
    exercicios = database.listar_exercicios_cargo(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_exercicios_cargo.html',
        {'exercicios': exercicios}
    )


# ==========================================
# ASSOCIACAO
# ==========================================

@direcao_required
def registar_associacao(request):
    if request.method == 'POST':
        form = AssociacaoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            # Verificar se o NIPC já está registado
            if database.associacao_existe_nipc(dados['nipc']):
                form.add_error('nipc', 'Este NIPC já está registado no sistema.')
                return render(
                    request,
                    'associacao/registar_associacao.html',
                    {'form': form, 'base_template': 'base.html'}
                )

            # Transformar a palavra-passe num hash seguro.
            password_hash = make_password(dados['password'])

            id_localidade = dados['id_localidade']
            if id_localidade:
                id_localidade = int(id_localidade)
            else:
                id_localidade = None

            database.inserir_associacao(
                dados['nipc'],
                dados['nome'],
                dados['data_fundacao'],
                dados['email'],
                dados['telefone'],
                password_hash,
                dados['tipo_via'],
                dados['nome_via'],
                dados['numero_porta'],
                dados['andar'],
                dados['codigo_postal'],
                id_localidade
            )

            return redirect('listar_associacoes')

    else:
        form = AssociacaoForm()

    return render(
        request,
        'associacao/registar_associacao.html',
        {'form': form, 'base_template': 'base.html'}
    )


def registar_associacao_publico(request):
    """
    Vista pública para registar uma associação (sem autenticação).
    Permite criar múltiplas associações.
    """
    if request.method == 'POST':
        form = AssociacaoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            # Verificar se o NIPC já está registado
            if database.associacao_existe_nipc(dados['nipc']):
                form.add_error('nipc', 'Este NIPC já está registado no sistema.')
                return render(
                    request,
                    'associacao/registar_associacao.html',
                    {'form': form, 'publico': True, 'base_template': 'base_publico.html'}
                )

            # Transformar a palavra-passe num hash seguro.
            password_hash = make_password(dados['password'])

            id_localidade = dados['id_localidade']
            if id_localidade:
                id_localidade = int(id_localidade)
            else:
                id_localidade = None

            database.inserir_associacao(
                dados['nipc'],
                dados['nome'],
                dados['data_fundacao'],
                dados['email'],
                dados['telefone'],
                password_hash,
                dados['tipo_via'],
                dados['nome_via'],
                dados['numero_porta'],
                dados['andar'],
                dados['codigo_postal'],
                id_localidade
            )

            return redirect('login')

    else:
        form = AssociacaoForm()

    return render(
        request,
        'associacao/registar_associacao.html',
        {'form': form, 'publico': True, 'base_template': 'base_publico.html'}
    )


@direcao_required
def listar_associacoes(request):
    associacoes = database.listar_associacoes()
    # Get current user's association
    associacao = None
    if hasattr(request.user, 'id_associacao'):
        associacao = database.obter_associacao(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_associacoes.html',
        {'associacoes': associacoes, 'associacao': associacao}
    )


# ==========================================
# EVENTO
# ==========================================

@direcao_required
def registar_evento(request):
    id_associacao = request.user.id_associacao

    if request.method == 'POST':
        form = EventoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            database.inserir_evento(
                dados['nome_evento'],
                dados['descricao_evento'],
                dados['data_inicio_evento'],
                dados['data_fim_evento'],
                dados['local_evento'],
                dados['estado_evento'],
                id_associacao
            )

            messages.success(request, 'Evento registado com sucesso.')
            return redirect('listar_eventos')

    else:
        form = EventoForm()

    return render(
        request,
        'associacao/registar_evento.html',
        {'form': form}
    )


@direcao_required
def listar_eventos(request):
    data_inicial = request.GET.get('data_inicial', '')
    data_final = request.GET.get('data_final', '')
    filtros = [request.user.id_associacao]
    clausulas = ['id_associacao = %s']

    for parametro, operador in ((data_inicial, '>='), (data_final, '<=')):
        if parametro:
            try:
                filtros.append(datetime.strptime(parametro, '%Y-%m-%d').date())
                clausulas.append(f'data_inicio_evento::date {operador} %s')
            except ValueError:
                if operador == '>=':
                    data_inicial = ''
                else:
                    data_final = ''

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM vw_eventos WHERE {' AND '.join(clausulas)} ORDER BY data_inicio_evento DESC;",
            filtros,
        )
        eventos = cursor.fetchall()

    return render(
        request,
        'associacao/listar_eventos.html',
        {'eventos': eventos, 'data_inicial': data_inicial, 'data_final': data_final}
    )


# ==========================================
# ASSOCIADO
# ==========================================

@direcao_required
def registar_associado(request):
    id_associacao = request.user.id_associacao

    if request.method == "POST":
        form = AssociadoForm(request.POST, id_associacao=id_associacao)

        if form.is_valid():
            dados = form.cleaned_data

            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # Se a pessoa já tem conta noutra associação, preservar
                        # as credenciais e o estado do primeiro acesso.
                        cursor.execute(
                            """SELECT password_hash, exigir_alteracao_password
                               FROM associado WHERE nif = %s AND password_hash IS NOT NULL
                               ORDER BY id_associado LIMIT 1 FOR UPDATE""",
                            [dados['nif']],
                        )
                        conta_existente = cursor.fetchone()

                        cursor.execute(
                            '''SELECT 1 FROM associado
                               WHERE numero_associado = %s AND id_associacao = %s''',
                            [dados['numero_associado'], id_associacao],
                        )
                        if cursor.fetchone():
                            form.add_error('numero_associado', 'Este número de associado já se encontra registado.')
                            return render(request, 'associacao/registar_associado.html', {'form': form})

                        database.inserir_associado(
                            dados["numero_associado"], dados["nome"], dados["nif"],
                            dados["data_nascimento"], dados["email"], dados["telefone"],
                            dados["data_adesao"], dados["data_saida"], dados["estado"],
                            dados["tipo_via"], dados["nome_via"], dados["numero_porta"],
                            dados["andar"], dados["codigo_postal"],
                            int(dados["id_localidade"]) if dados["id_localidade"] else None,
                            id_associacao,
                        )

                        if conta_existente:
                            password_hash, exigir_alteracao_password = conta_existente
                            cursor.execute(
                                """UPDATE associado SET password_hash = %s,
                                          exigir_alteracao_password = %s
                                   WHERE id_associacao = %s AND numero_associado = %s""",
                                [password_hash, exigir_alteracao_password,
                                 id_associacao, dados['numero_associado']],
                            )
                        else:
                            palavra_passe_temporaria = secrets.token_urlsafe(12)
                            password_hash = make_password(palavra_passe_temporaria)
                            cursor.execute(
                                """UPDATE associado SET password_hash = %s,
                                          exigir_alteracao_password = TRUE
                                   WHERE id_associacao = %s AND numero_associado = %s""",
                                [password_hash, id_associacao, dados['numero_associado']],
                            )
            except IntegrityError as error:
                if getattr(error.__cause__, 'diag', None) and error.__cause__.diag.constraint_name == 'uq_associado_associacao_numero':
                    form.add_error('numero_associado', 'Este número de associado já se encontra registado.')
                    return render(request, 'associacao/registar_associado.html', {'form': form})
                raise
            registar_auditoria(request, 'create', 'associado', details={
                'numero_associado': dados['numero_associado'],
                'conta_existente': bool(conta_existente),
            })
            if conta_existente:
                return render(request, 'associacao/credenciais_associado_criadas.html', {
                    'associado_nome': dados['nome'],
                    'associado_nif': dados['nif'],
                    'conta_existente': True,
                })
            return render(request, 'associacao/credenciais_associado_criadas.html', {
                'associado_nome': dados['nome'], 'associado_nif': dados['nif'],
                'palavra_passe_temporaria': palavra_passe_temporaria,
            })

    else:
        form = AssociadoForm(id_associacao=id_associacao)

    return render(
        request,
        "associacao/registar_associado.html",
        {"form": form}
    )


@direcao_required
def listar_associados(request):
    associados = database.listar_associados_completos(request.user.id_associacao)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FILTER (WHERE estado = 'Ativo'),
                   COUNT(*) FILTER (WHERE estado = 'Inativo')
            FROM associado
            WHERE id_associacao = %s
        """, [request.user.id_associacao])
        total_ativos, total_inativos = cursor.fetchone()

    return render(
        request,
        "associacao/listar_associados.html",
        {"associados": associados, "total_ativos": total_ativos, "total_inativos": total_inativos}
    )


# ==========================================
# QUOTA
# ==========================================

@direcao_required
def registar_quota(request):
    id_associacao = request.user.id_associacao

    if request.method == "POST":
        form = QuotaForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            database.inserir_quota(
                dados["designacao_quota"],
                dados["valor_quota"],
                dados["periodicidade_quota"],
                dados["data_inicio_quota"],
                dados["data_fim_quota"],
                id_associacao
            )
            registar_auditoria(request, 'create', 'quota', details={'designacao': dados['designacao_quota']})

            messages.success(request, 'Quota registada com sucesso.')
            return redirect("listar_quotas")

    else:
        form = QuotaForm()

    return render(
        request,
        "associacao/registar_quota.html",
        {"form": form}
    )


@direcao_required
def listar_quotas(request):
    quotas = database.listar_quotas(request.user.id_associacao)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE data_vencimento >= date_trunc('year', CURRENT_DATE)),
                COUNT(*) FILTER (WHERE estado_efetivo = 'Pago'),
                COUNT(*) FILTER (WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')),
                COALESCE(SUM(GREATEST(valor_devido - total_pago, 0))
                    FILTER (WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')), 0)
            FROM vw_quota_associado_estado_efetivo
            WHERE id_associacao = %s
        """, [request.user.id_associacao])
        quotas_ano, quotas_pagas, quotas_pendentes, valor_pendente = cursor.fetchone()
    percent_pagas = round((quotas_pagas / (quotas_pagas + quotas_pendentes)) * 100) if quotas_pagas + quotas_pendentes else 0

    return render(
        request,
        "associacao/listar_quotas.html",
        {
            "quotas": quotas,
            "quotas_ano": quotas_ano,
            "quotas_pagas": quotas_pagas,
            "quotas_pendentes": quotas_pendentes,
            "valor_pendente": valor_pendente,
            "percent_pagas": percent_pagas,
        }
    )


# ==========================================
# ÓRGÃO SOCIAL
# ==========================================

@direcao_required
def registar_orgao_social(request):
    id_associacao = request.user.id_associacao

    if request.method == "POST":
        form = OrgaoSocialForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            try:
                with transaction.atomic():
                    database.inserir_orgao_social(
                        dados["nome"],
                        dados["descricao"],
                        id_associacao
                    )
            except IntegrityError:
                form.add_error('nome', 'Já existe um órgão social com este nome nesta associação.')
                return render(request, 'associacao/registar_orgao_social.html', {'form': form})
            registar_auditoria(request, 'create', 'orgao_social', details={'nome': dados['nome']})

            messages.success(request, 'Órgão social registado com sucesso.')
            return redirect("listar_orgaos_sociais")
    else:
        form = OrgaoSocialForm()

    return render(
        request,
        "associacao/registar_orgao_social.html",
        {"form": form}
    )


@direcao_required
def listar_orgaos_sociais(request):
    orgaos = database.listar_orgaos_sociais(request.user.id_associacao)

    return render(
        request,
        "associacao/listar_orgaos_sociais.html",
        {"orgaos": orgaos}
    )


# ==========================================
# CARGO
# ==========================================

@direcao_required
def registar_cargo(request):
    if request.method == "POST":
        form = CargoForm(request.POST, id_associacao=request.user.id_associacao)

        if form.is_valid():
            dados = form.cleaned_data

            try:
                with transaction.atomic():
                    database.inserir_cargo(
                        dados["nome"],
                        dados["descricao"],
                        int(dados["id_orgao_social"]),
                        request.user.id_associacao
                    )
            except IntegrityError:
                form.add_error('nome', 'Já existe um cargo com este nome neste órgão social.')
                return render(request, 'associacao/registar_cargo.html', {'form': form})
            registar_auditoria(request, 'create', 'cargo', details={'nome': dados['nome']})

            messages.success(request, 'Cargo registado com sucesso.')
            return redirect("listar_cargos")
    else:
        form = CargoForm(id_associacao=request.user.id_associacao)

    return render(
        request,
        "associacao/registar_cargo.html",
        {"form": form}
    )


@direcao_required
def listar_cargos(request):
    cargos = database.listar_cargos_completos(request.user.id_associacao)

    return render(
        request,
        "associacao/listar_cargos.html",
        {"cargos": cargos}
    )


# ==========================================
# EDIT/DELETE VIEWS
# ==========================================

# Mandato
@direcao_required
def editar_mandato(request, id_mandato):
    mandato = database.obter_mandato(id_mandato)
    if not mandato:
        messages.error(request, 'Mandato não encontrado.')
        return redirect('listar_mandatos')

    if request.method == 'POST':
        form = MandatoForm(request.POST)
        if form.is_valid():
            if database.mandato_sobrepoe(form.cleaned_data['data_inicio'], form.cleaned_data['data_fim'], mandato[3], id_mandato):
                form.add_error(None, 'O mandato sobrepõe-se a um mandato já registado.')
                return render(request, 'associacao/registar_mandato.html', {'form': form, 'editar': True, 'id': id_mandato})
            try:
                database.atualizar_mandato(
                    form.cleaned_data['data_inicio'],
                    form.cleaned_data['data_fim'],
                    mandato[3],  # Keep original id_associacao
                    id_mandato
                )
            except Exception as error:
                form.add_error(None, str(error))
                return render(request, 'associacao/registar_mandato.html', {'form': form, 'editar': True, 'id': id_mandato})
            registar_auditoria(request, 'update', 'mandato', id_mandato)
            messages.success(request, 'Mandato atualizado com sucesso.')
            return redirect('listar_mandatos')
    else:
        # Preencher form com dados existentes (sem id_associacao)
        form = MandatoForm(initial={
            'data_inicio': mandato[1],
            'data_fim': mandato[2],
        })

    return render(request, 'associacao/registar_mandato.html', {'form': form, 'editar': True, 'id': id_mandato})


@direcao_required
def eliminar_mandato(request, id_mandato):
    if request.method == 'POST':
        # Verificar se o mandato pertence à associação autenticada
        mandato = database.obter_mandato(id_mandato)
        if mandato and mandato[3] == request.user.id_associacao:  # id_associacao is at index 3 in vw_mandatos
            database.eliminar_mandato(id_mandato, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'mandato', id_mandato)
            messages.success(request, 'Mandato eliminado com sucesso.')
        else:
            messages.error(request, 'Mandato não encontrado.')
    return redirect('listar_mandatos')


# ExercicioCargo
@direcao_required
def editar_exercicio_cargo(request, id_exercicio_cargo):
    exercicio = database.obter_exercicio_cargo(id_exercicio_cargo)
    if not exercicio:
        messages.error(request, 'Exercício de cargo não encontrado.')
        return redirect('listar_exercicios_cargo')

    # Verificar se o exercício pertence à associação autenticada
    # vw_exercicios_cargo tem id_associacao no final (posição 12)
    exercicio_associacao = exercicio[-1] if len(exercicio) > 12 else None
    if exercicio_associacao != request.user.id_associacao:
        messages.error(request, 'Exercício de cargo não encontrado.')
        return redirect('listar_exercicios_cargo')

    if request.method == 'POST':
        form = ExercicioCargoForm(request.POST, id_associacao=request.user.id_associacao)
        if form.is_valid():
            database.atualizar_exercicio_cargo(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                int(form.cleaned_data['id_associado']),
                int(form.cleaned_data['id_cargo']),
                int(form.cleaned_data['id_mandato']),
                id_exercicio_cargo,
                request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'exercicio_cargo', id_exercicio_cargo)
            messages.success(request, 'Exercício de cargo atualizado com sucesso.')
            return redirect('listar_exercicios_cargo')
    else:
        form = ExercicioCargoForm(initial={
            'data_inicio': exercicio[1],
            'data_fim': exercicio[2],
            'id_associado': str(exercicio[3]),
            'id_cargo': str(exercicio[5]),
            'id_mandato': str(exercicio[9]),
        }, id_associacao=request.user.id_associacao)

    return render(request, 'associacao/registar_exercicio_cargo.html', {'form': form, 'editar': True, 'id': id_exercicio_cargo})


@direcao_required
def eliminar_exercicio_cargo(request, id_exercicio_cargo):
    if request.method == 'POST':
        # Verificar se o exercício pertence à associação autenticada
        exercicio = database.obter_exercicio_cargo(id_exercicio_cargo)
        if exercicio and len(exercicio) > 12 and exercicio[-1] == request.user.id_associacao:
            database.eliminar_exercicio_cargo(id_exercicio_cargo, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'exercicio_cargo', id_exercicio_cargo)
            messages.success(request, 'Exercício de cargo eliminado com sucesso.')
        else:
            messages.error(request, 'Exercício de cargo não encontrado.')
    return redirect('listar_exercicios_cargo')


# Associacao
@direcao_required
def editar_associacao(request, id_associacao):
    associacao = database.obter_associacao(id_associacao)
    if not associacao:
        messages.error(request, 'Associação não encontrada.')
        return redirect('listar_associacoes')

    if request.method == 'POST':
        form = AssociacaoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            password_hash = dados['password'] if dados['password'] else associacao[28] if len(associacao) > 28 else None
            # O AssociacaoForm não tem campo password no model, mas no form sim
            # Vamos verificar se o password foi alterado
            id_localidade = int(dados['id_localidade']) if dados['id_localidade'] else None

            database.atualizar_associacao(
                id_associacao,
                dados['nipc'], dados['nome'], dados['data_fundacao'],
                dados['email'], dados['telefone'], password_hash,
                dados['tipo_via'], dados['nome_via'], dados['numero_porta'],
                dados['andar'], dados['codigo_postal'], id_localidade
            )
            if dados['password']:
                registar_auditoria(request, 'credentials_changed', 'associacao', id_associacao)
            messages.success(request, 'Associação atualizada com sucesso.')
            return redirect('listar_associacoes')
    else:
        # Obter o nome da localidade para preencher o campo readonly
        localidade_nome = associacao[13] if associacao[13] else ''

        form = AssociacaoForm(initial={
            'nipc': associacao[1],
            'nome': associacao[2],
            'data_fundacao': associacao[3],
            'email': associacao[4],
            'telefone': associacao[5],
            'password': '',  # Não pré-preencher password
            'tipo_via': associacao[7],
            'nome_via': associacao[8],
            'numero_porta': associacao[9],
            'andar': associacao[10],
            'codigo_postal': associacao[11],
            'id_localidade': associacao[12] if associacao[12] else None,
        })
        # Adicionar o nome da localidade ao form para o template
        form.localidade_nome = localidade_nome

    return render(request, 'associacao/editar_associacao.html', {'form': form, 'id': id_associacao})


@direcao_required
def eliminar_associacao(request, id_associacao):
    # A Direção não pode eliminar associações através da interface administrativa
    # Apenas superadministradores (não implementado) poderiam fazer isso
    messages.error(request, 'Operação não permitida. Contacte o administrador do sistema.')
    return redirect('listar_associacoes')


# Evento
@direcao_required
def editar_evento(request, id_evento):
    evento = database.obter_evento(id_evento)
    if not evento:
        messages.error(request, 'Evento não encontrado.')
        return redirect('listar_eventos')

    # Verificar se o evento pertence à associação autenticada
    # vw_eventos tem id_associacao no final (índice -1 ou posição 8)
    evento_associacao = evento[-1] if len(evento) > 8 else None
    if evento_associacao != request.user.id_associacao:
        messages.error(request, 'Evento não encontrado.')
        return redirect('listar_eventos')

    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_evento(
                id_evento,
                dados['nome_evento'], dados['descricao_evento'],
                dados['data_inicio_evento'], dados['data_fim_evento'],
                dados['local_evento'], dados['estado_evento'], request.user.id_associacao
            )
            messages.success(request, 'Evento atualizado com sucesso.')
            return redirect('listar_eventos')
    else:
        form = EventoForm(initial={
            'nome_evento': evento[1],
            'descricao_evento': evento[2],
            'data_inicio_evento': evento[3],
            'data_fim_evento': evento[4],
            'local_evento': evento[5],
            'estado_evento': evento[6],
        })

    return render(request, 'associacao/registar_evento.html', {'form': form, 'editar': True, 'id': id_evento})


@direcao_required
def eliminar_evento(request, id_evento):
    if request.method == 'POST':
        # Verificar se o evento pertence à associação autenticada
        evento = database.obter_evento(id_evento)
        if evento and len(evento) > 8 and evento[-1] == request.user.id_associacao:
            database.eliminar_evento(id_evento, request.user.id_associacao)
            messages.success(request, 'Evento eliminado com sucesso.')
        else:
            messages.error(request, 'Evento não encontrado.')
    return redirect('listar_eventos')


# Associado
@direcao_required
def editar_associado(request, id_associado):
    associado = database.obter_associado(id_associado)
    if not associado:
        messages.error(request, 'Associado não encontrado.')
        return redirect('listar_associados')

    # Verificar se o associado pertence à associação autenticada
    # vw_associados tem id_associacao no final
    associado_associacao = associado[-1] if len(associado) > 17 else None
    if associado_associacao != request.user.id_associacao:
        messages.error(request, 'Associado não encontrado.')
        return redirect('listar_associados')

    if request.method == 'POST':
        form = AssociadoForm(request.POST, id_associacao=request.user.id_associacao)
        if form.is_valid():
            dados = form.cleaned_data

            # Handle password update separately if provided
            password_hash = None
            if dados['password']:
                from django.contrib.auth.hashers import make_password
                password_hash = make_password(dados['password'])

            database.atualizar_associado(
                id_associado,
                dados['numero_associado'], dados['nome'], dados['nif'],
                dados['data_nascimento'], dados['email'], dados['telefone'],
                dados['data_adesao'], dados['data_saida'], dados['estado'],
                dados['tipo_via'], dados['nome_via'], dados['numero_porta'],
                dados['andar'], dados['codigo_postal'],
                int(dados['id_localidade']) if dados['id_localidade'] else None,
                request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'associado', id_associado)

            # Update password if provided
            if password_hash:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE associado SET password_hash = %s WHERE id_associado = %s AND id_associacao = %s",
                        [password_hash, id_associado, request.user.id_associacao]
                    )
                registar_auditoria(request, 'credentials_changed', 'associado', id_associado)

            messages.success(request, 'Associado atualizado com sucesso.')
            return redirect('listar_associados')
    else:
        # Obter o nome da localidade para preencher o campo readonly
        localidade_nome = associado[16] if len(associado) > 16 and associado[16] else ''

        form = AssociadoForm(initial={
            'numero_associado': associado[1],
            'nome': associado[2],
            'nif': associado[3],
            'data_nascimento': associado[4],
            'email': associado[5],
            'telefone': associado[6],
            'data_adesao': associado[7],
            'data_saida': associado[8],
            'estado': associado[9],
            'tipo_via': associado[10],
            'nome_via': associado[11],
            'numero_porta': associado[12],
            'andar': associado[13],
            'codigo_postal': associado[14],
            'id_localidade': associado[15] if associado[15] else None,
        }, id_associacao=request.user.id_associacao)
        # Adicionar o nome da localidade ao form para o template
        form.localidade_nome = localidade_nome

    return render(request, 'associacao/registar_associado.html', {'form': form, 'editar': True, 'id': id_associado})


@direcao_required
def eliminar_associado(request, id_associado):
    id_associacao = request.user.id_associacao
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nome, nif FROM associado WHERE id_associado = %s AND id_associacao = %s",
            [id_associado, id_associacao],
        )
        associado = cursor.fetchone()

    if not associado:
        messages.error(request, 'Associado não encontrado.')
        return redirect('listar_associados')

    if request.method == 'POST' and request.POST.get('confirmar_eliminacao') == 'SIM':
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Registos exclusivamente dependentes desta inscrição.
                cursor.execute("""
                    DELETE FROM conciliacao_bancaria
                    WHERE id_associacao = %s
                      AND id_pagamento IN (
                        SELECT p.id_pagamento
                        FROM pagamento p
                        JOIN quota_associado qa ON qa.id_quota_associado = p.id_quota_associado
                        JOIN quota q ON q.id_quota = qa.id_quota
                        WHERE qa.id_associado = %s AND q.id_associacao = %s
                      )
                """, [id_associacao, id_associado, id_associacao])
                conciliacoes_removidas = cursor.rowcount
                cursor.execute("""
                    DELETE FROM pagamento p
                    USING quota_associado qa, quota q
                    WHERE p.id_quota_associado = qa.id_quota_associado
                      AND qa.id_quota = q.id_quota
                      AND qa.id_associado = %s AND q.id_associacao = %s
                """, [id_associado, id_associacao])
                pagamentos_removidos = cursor.rowcount
                cursor.execute("""
                    DELETE FROM quota_associado qa
                    USING quota q
                    WHERE qa.id_quota = q.id_quota
                      AND qa.id_associado = %s AND q.id_associacao = %s
                """, [id_associado, id_associacao])
                quotas_removidas = cursor.rowcount
                cursor.execute("""
                    DELETE FROM exercicio_cargo ec
                    USING cargo c, orgao_social os
                    WHERE ec.id_cargo = c.id_cargo
                      AND c.id_orgao_social = os.id_orgao_social
                      AND ec.id_associado = %s AND os.id_associacao = %s
                """, [id_associado, id_associacao])
                exercicios_removidos = cursor.rowcount
                cursor.execute(
                    "DELETE FROM associado WHERE id_associado = %s AND id_associacao = %s",
                    [id_associado, id_associacao],
                )

        registar_auditoria(request, 'delete', 'associado', id_associado, {
            'id_associacao': id_associacao,
            'nome': associado[0],
            'eliminacao_permanente': True,
            'quotas_removidas': quotas_removidas,
            'pagamentos_removidos': pagamentos_removidos,
            'conciliacoes_removidas': conciliacoes_removidas,
            'exercicios_cargo_removidos': exercicios_removidos,
        })
        messages.success(
            request,
            'Associado e respetivo histórico removidos permanentemente desta associação. '
            'Inscrições noutras associações e a conta global foram preservadas.',
        )
        return redirect('listar_associados')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
              (SELECT COUNT(*) FROM quota_associado qa JOIN quota q ON q.id_quota = qa.id_quota
               WHERE qa.id_associado = %s AND q.id_associacao = %s),
              (SELECT COUNT(*) FROM pagamento p JOIN quota_associado qa ON qa.id_quota_associado = p.id_quota_associado
               JOIN quota q ON q.id_quota = qa.id_quota WHERE qa.id_associado = %s AND q.id_associacao = %s),
              (SELECT COUNT(*) FROM exercicio_cargo ec JOIN associado a ON a.id_associado = ec.id_associado
               JOIN cargo c ON c.id_cargo = ec.id_cargo JOIN orgao_social os ON os.id_orgao_social = c.id_orgao_social
               WHERE ec.id_associado = %s AND a.id_associacao = %s AND os.id_associacao = %s)
        """, [id_associado, id_associacao, id_associado, id_associacao,
              id_associado, id_associacao, id_associacao])
        total_quotas, total_pagamentos, total_cargos = cursor.fetchone()
        cursor.execute("""
            SELECT COUNT(*) FROM conciliacao_bancaria cb
            JOIN pagamento p ON p.id_pagamento = cb.id_pagamento
            JOIN quota_associado qa ON qa.id_quota_associado = p.id_quota_associado
            JOIN quota q ON q.id_quota = qa.id_quota
            WHERE qa.id_associado = %s AND q.id_associacao = %s AND cb.id_associacao = %s
        """, [id_associado, id_associacao, id_associacao])
        total_conciliacoes = cursor.fetchone()[0]

    return render(request, 'associacao/confirmar_eliminar_associado.html', {
        'associado': associado,
        'id_associado': id_associado,
        'total_quotas': total_quotas,
        'total_pagamentos': total_pagamentos,
        'total_conciliacoes': total_conciliacoes,
        'total_cargos': total_cargos,
    })


# Quota
@direcao_required
def editar_quota(request, id_quota):
    quota = database.obter_quota(id_quota)
    if not quota:
        messages.error(request, 'Quota não encontrada.')
        return redirect('listar_quotas')

    # Verificar se a quota pertence à associação autenticada
    # vw_quotas tem id_associacao no final
    quota_associacao = quota[-1] if len(quota) > 6 else None
    if quota_associacao != request.user.id_associacao:
        messages.error(request, 'Quota não encontrada.')
        return redirect('listar_quotas')

    if request.method == 'POST':
        form = QuotaForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_quota(
                id_quota,
                dados['designacao_quota'], dados['valor_quota'],
                dados['periodicidade_quota'], dados['data_inicio_quota'],
                dados['data_fim_quota'], request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'quota', id_quota)
            messages.success(request, 'Quota atualizada com sucesso.')
            return redirect('listar_quotas')
    else:
        form = QuotaForm(initial={
            'designacao_quota': quota[1],
            'valor_quota': quota[2],
            'periodicidade_quota': quota[3],
            'data_inicio_quota': quota[4],
            'data_fim_quota': quota[5],
        })

    return render(request, 'associacao/registar_quota.html', {'form': form, 'editar': True, 'id': id_quota})


@direcao_required
def eliminar_quota(request, id_quota):
    if request.method == 'POST':
        # Verificar se a quota pertence à associação autenticada
        quota = database.obter_quota(id_quota)
        if quota and len(quota) > 6 and quota[-1] == request.user.id_associacao:
            database.eliminar_quota(id_quota, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'quota', id_quota)
            messages.success(request, 'Quota eliminada com sucesso.')
        else:
            messages.error(request, 'Quota não encontrada.')
    return redirect('listar_quotas')


# OrgaoSocial
@direcao_required
def editar_orgao_social(request, id_orgao_social):
    orgao = database.obter_orgao_social(id_orgao_social)
    if not orgao:
        messages.error(request, 'Órgão social não encontrado.')
        return redirect('listar_orgaos_sociais')

    # Verificar se o órgão pertence à associação autenticada
    # vw_orgaos_sociais tem id_associacao no final
    orgao_associacao = orgao[-1] if len(orgao) > 3 else None
    if orgao_associacao != request.user.id_associacao:
        messages.error(request, 'Órgão social não encontrado.')
        return redirect('listar_orgaos_sociais')

    if request.method == 'POST':
        form = OrgaoSocialForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_orgao_social(
                id_orgao_social, dados['nome'], dados['descricao'], request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'orgao_social', id_orgao_social)
            messages.success(request, 'Órgão social atualizado com sucesso.')
            return redirect('listar_orgaos_sociais')
    else:
        form = OrgaoSocialForm(initial={
            'nome': orgao[1],
            'descricao': orgao[2],
        })

    return render(request, 'associacao/registar_orgao_social.html', {'form': form, 'editar': True, 'id': id_orgao_social})


@direcao_required
def eliminar_orgao_social(request, id_orgao_social):
    if request.method == 'POST':
        # Verificar se o órgão pertence à associação autenticada
        orgao = database.obter_orgao_social(id_orgao_social)
        if orgao and len(orgao) > 3 and orgao[-1] == request.user.id_associacao:
            database.eliminar_orgao_social(id_orgao_social, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'orgao_social', id_orgao_social)
            messages.success(request, 'Órgão social eliminado com sucesso.')
        else:
            messages.error(request, 'Órgão social não encontrado.')
    return redirect('listar_orgaos_sociais')


# Cargo
@direcao_required
def editar_cargo(request, id_cargo):
    cargo = database.obter_cargo(id_cargo)
    if not cargo:
        messages.error(request, 'Cargo não encontrado.')
        return redirect('listar_cargos')

    # Verificar se o cargo pertence à associação autenticada via orgao_social
    # vw_cargos tem id_associacao no final (posição 5)
    cargo_associacao = cargo[5] if len(cargo) > 5 else None
    if cargo_associacao != request.user.id_associacao:
        messages.error(request, 'Cargo não encontrado.')
        return redirect('listar_cargos')

    if request.method == 'POST':
        form = CargoForm(request.POST, id_associacao=request.user.id_associacao)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_cargo(
                id_cargo, dados['nome'], dados['descricao'], int(dados['id_orgao_social']), request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'cargo', id_cargo)
            messages.success(request, 'Cargo atualizado com sucesso.')
            return redirect('listar_cargos')
    else:
        form = CargoForm(initial={
            'nome': cargo[1],
            'descricao': cargo[2],
            'id_orgao_social': str(cargo[3]),
        }, id_associacao=request.user.id_associacao)

    return render(request, 'associacao/registar_cargo.html', {'form': form, 'editar': True, 'id': id_cargo})


@direcao_required
def eliminar_cargo(request, id_cargo):
    if request.method == 'POST':
        # Verificar se o cargo pertence à associação autenticada
        cargo = database.obter_cargo(id_cargo)
        if cargo and len(cargo) > 5 and cargo[5] == request.user.id_associacao:
            database.eliminar_cargo(id_cargo, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'cargo', id_cargo)
            messages.success(request, 'Cargo eliminado com sucesso.')
        else:
            messages.error(request, 'Cargo não encontrado.')
    return redirect('listar_cargos')


# QuotaAssociado
@direcao_required
def listar_quotas_associado(request):
    quotas = database.listar_quotas_associado(request.user.id_associacao)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE data_vencimento >= date_trunc('year', CURRENT_DATE)),
                COUNT(*) FILTER (WHERE estado_efetivo = 'Pago'),
                COUNT(*) FILTER (WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')),
                COALESCE(SUM(GREATEST(valor_devido - total_pago, 0))
                    FILTER (WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')), 0)
            FROM vw_quota_associado_estado_efetivo
            WHERE id_associacao = %s
        """, [request.user.id_associacao])
        quotas_ano, quotas_pagas, quotas_pendentes, valor_pendente = cursor.fetchone()
    percent_pagas = round((quotas_pagas / (quotas_pagas + quotas_pendentes)) * 100) if quotas_pagas + quotas_pendentes else 0
    return render(request, 'associacao/listar_quotas_associado.html', {
        'quotas': quotas,
        'quotas_ano': quotas_ano,
        'quotas_pagas': quotas_pagas,
        'quotas_pendentes': quotas_pendentes,
        'valor_pendente': valor_pendente,
        'percent_pagas': percent_pagas,
    })


@direcao_required
def gerar_quotas_associados_view(request):
    if request.method == 'POST':
        from .forms import GerarQuotasForm
        form = GerarQuotasForm(request.POST, id_associacao=request.user.id_associacao)
        if form.is_valid():
            database.gerar_quotas_associados(
                int(form.cleaned_data['id_quota']),
                form.cleaned_data['data_vencimento_inicial'],
                form.cleaned_data['periodos']
            )
            registar_auditoria(request, 'generate', 'quota_associado', details={'id_quota': int(form.cleaned_data['id_quota']), 'periodos': form.cleaned_data['periodos']})
            messages.success(request, 'Quotas geradas com sucesso para todos os associados ativos.')
            return redirect('listar_quotas_associado')
    else:
        from .forms import GerarQuotasForm
        form = GerarQuotasForm(id_associacao=request.user.id_associacao)

    return render(request, 'associacao/gerar_quotas_associados.html', {'form': form})


@direcao_required
def editar_quota_associado(request, id_quota_associado):
    quota_assoc = database.obter_quota_associado(id_quota_associado)
    if not quota_assoc:
        messages.error(request, 'Quota do associado não encontrada.')
        return redirect('listar_quotas_associado')

    # Verificar se a quota_associado pertence à associação autenticada
    # Precisamos verificar via quota -> id_associacao
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT q.id_associacao
            FROM quota_associado qa
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE qa.id_quota_associado = %s
        """, [id_quota_associado])
        row = cursor.fetchone()

    if not row or row[0] != request.user.id_associacao:
        messages.error(request, 'Quota do associado não encontrada.')
        return redirect('listar_quotas_associado')

    if request.method == 'POST':
        from .forms import QuotaAssociadoForm
        form = QuotaAssociadoForm(request.POST, id_associacao=request.user.id_associacao)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_quota_associado(
                id_quota_associado,
                dados['valor_devido'], dados['data_vencimento'],
                dados['periodo_referencia'], dados['estado_quota_associado'],
                int(dados['id_associado']), int(dados['id_quota']),
                request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'quota_associado', id_quota_associado)
            messages.success(request, 'Quota do associado atualizada com sucesso.')
            return redirect('listar_quotas_associado')
    else:
        from .forms import QuotaAssociadoForm
        form = QuotaAssociadoForm(initial={
            'valor_devido': quota_assoc[2],
            'data_vencimento': quota_assoc[3],
            'periodo_referencia': quota_assoc[4],
            'estado_quota_associado': quota_assoc[5],
            'id_associado': str(quota_assoc[6]),
            'id_quota': str(quota_assoc[7]),
        }, id_associacao=request.user.id_associacao)

    return render(request, 'associacao/editar_quota_associado.html', {'form': form, 'editar': True, 'id': id_quota_associado})


@direcao_required
def eliminar_quota_associado(request, id_quota_associado):
    if request.method == 'POST':
        # Verificar se a quota_associado pertence à associação autenticada
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT q.id_associacao
                FROM quota_associado qa
                JOIN quota q ON qa.id_quota = q.id_quota
                WHERE qa.id_quota_associado = %s
            """, [id_quota_associado])
            row = cursor.fetchone()

        if row and row[0] == request.user.id_associacao:
            database.eliminar_quota_associado(id_quota_associado, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'quota_associado', id_quota_associado)
            messages.success(request, 'Quota do associado eliminada com sucesso.')
        else:
            messages.error(request, 'Quota do associado não encontrada.')
    return redirect('listar_quotas_associado')


# ==========================================
# DASHBOARDS
# ==========================================

@direcao_required
def dashboard_direcao(request):
    """
    Dashboard da Direção com métricas principais e acessos rápidos.
    """
    with connection.cursor() as cursor:
        # Total de associados ativos
        cursor.execute("""
            SELECT COUNT(*) FROM associado
            WHERE estado = 'Ativo' AND id_associacao = %s
        """, [request.user.id_associacao])
        total_ativos = cursor.fetchone()[0]

        # Quotas em dívida (estado = 'Pendente' ou 'Em Dívida')
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(GREATEST(valor_devido - total_pago, 0)), 0)
            FROM vw_quota_associado_estado_efetivo
            WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')
            AND id_associacao = %s
        """, [request.user.id_associacao])
        quotas_pendentes_count, quotas_pendentes_valor = cursor.fetchone()

        # Total recebido (pagamentos confirmados)
        cursor.execute("""
            SELECT COALESCE(SUM(valor_pago), 0)
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE q.id_associacao = %s
        """, [request.user.id_associacao])
        total_recebido = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*), COUNT(DISTINCT p.id_quota_associado)
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE q.id_associacao = %s
        """, [request.user.id_associacao])
        pagamentos_count, quotas_pagas = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) FROM vw_quota_associado_estado_efetivo
            WHERE id_associacao = %s
        """, [request.user.id_associacao])
        quotas_total = cursor.fetchone()[0]

        # Próximos eventos (próximos 30 dias)
        cursor.execute("""
            SELECT id_evento, nome_evento, data_inicio_evento, local_evento, estado_evento
            FROM evento
            WHERE id_associacao = %s
            AND data_inicio_evento >= NOW()
            AND data_inicio_evento <= NOW() + INTERVAL '30 days'
            ORDER BY data_inicio_evento
            LIMIT 5
        """, [request.user.id_associacao])
        proximos_eventos = cursor.fetchall()

        # Pagamentos recentes (últimos 10)
        cursor.execute("""
            SELECT p.id_pagamento, p.data_pagamento, p.valor_pago, p.metodo_pagamento,
                   a.numero_associado, a.nome as associado_nome
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN associado a ON qa.id_associado = a.id_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE q.id_associacao = %s
            ORDER BY p.data_pagamento DESC
            LIMIT 10
        """, [request.user.id_associacao])
        pagamentos_recentes = cursor.fetchall()

    context = {
        'total_ativos': total_ativos,
        'quotas_pendentes_count': quotas_pendentes_count,
        'total_pendente': quotas_pendentes_valor,
        'total_recebido': total_recebido,
        'pagamentos_count': pagamentos_count,
        'quotas_pagas': quotas_pagas,
        'quotas_total': quotas_total,
        'proximos_eventos': proximos_eventos,
        'pagamentos_recentes': pagamentos_recentes,
    }

    return render(request, 'associacao/dashboard_direcao.html', context)


@associado_required
def dashboard_associado(request):
    """
    Dashboard simplificado do Associado.
    """
    with connection.cursor() as cursor:
        # Total de associados ativos na associação
        cursor.execute("""
            SELECT COUNT(*) FROM associado
            WHERE estado = 'Ativo' AND id_associacao = %s
        """, [request.user.id_associacao])
        total_ativos = cursor.fetchone()[0]

        # Próximos eventos (próximos 30 dias)
        cursor.execute("""
            SELECT id_evento, nome_evento, data_inicio_evento, data_fim_evento, local_evento, estado_evento
            FROM evento
            WHERE id_associacao = %s
            AND data_inicio_evento >= NOW()
            ORDER BY data_inicio_evento
            LIMIT 3
        """, [request.user.id_associacao])
        proximos_eventos = cursor.fetchall()

        # Resumo das quotas do associado
        cursor.execute("""
            SELECT
                COUNT(*) as total_quotas,
                COUNT(*) FILTER (WHERE estado_efetivo = 'Pago') as quotas_pagas,
                COUNT(*) FILTER (WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')) as quotas_pendentes,
                COALESCE(SUM(GREATEST(valor_devido - total_pago, 0)) FILTER (WHERE estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')), 0),
                COUNT(*) FILTER (WHERE data_vencimento < CURRENT_DATE AND estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')),
                COALESCE(SUM(GREATEST(valor_devido - total_pago, 0)) FILTER (WHERE data_vencimento < CURRENT_DATE AND estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')), 0),
                COALESCE(SUM(GREATEST(valor_devido - total_pago, 0)) FILTER (WHERE data_vencimento > CURRENT_DATE AND estado_efetivo IN ('Pendente', 'Em Dívida', 'Parcial')), 0)
            FROM vw_quota_associado_estado_efetivo
            WHERE id_associado = %s
        """, [request.user.id_associado])
        quotas_resumo = cursor.fetchone()

        # Informação da associação
        cursor.execute("""
            SELECT nome, email, telefone
            FROM associacao
            WHERE id_associacao = %s
        """, [request.user.id_associacao])
        associacao_info = cursor.fetchone()

    context = {
        'total_ativos': total_ativos,
        'associacao_nome': associacao_info[0] if associacao_info else '',
        'associacao_email': associacao_info[1] if associacao_info else '',
        'associacao_telefone': associacao_info[2] if associacao_info else '',
        'proximos_eventos': proximos_eventos,
        'quotas_resumo': {
            'total': quotas_resumo[0] if quotas_resumo else 0,
            'pagas': quotas_resumo[1] if quotas_resumo else 0,
            'pendentes': quotas_resumo[2] if quotas_resumo else 0,
            'valor_pendente': quotas_resumo[3] if quotas_resumo else 0,
            'vencidas': quotas_resumo[4] if quotas_resumo else 0,
            'valor_vencido': quotas_resumo[5] if quotas_resumo else 0,
            'valor_futuro': quotas_resumo[6] if quotas_resumo else 0,
        },
        'associacao_info': associacao_info,
    }

    return render(request, 'associacao/dashboard_associado.html', context)


# ==========================================
# PORTAL DO ASSOCIADO
# ==========================================

@associado_required
def portal_eventos(request):
    """
    Lista de eventos visíveis para o associado.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id_evento, nome_evento, descricao_evento, data_inicio_evento,
                   data_fim_evento, local_evento, estado_evento
            FROM evento
            WHERE id_associacao = %s
            ORDER BY data_inicio_evento DESC
        """, [request.user.id_associacao])
        eventos = cursor.fetchall()

    return render(request, 'associacao/portal/eventos.html', {'eventos': eventos})


@associado_required
def portal_associacao(request):
    """
    Informação institucional da associação para o associado.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT nome, data_fundacao, email, telefone,
                   tipo_via, nome_via, numero_porta, andar, a.codigo_postal,
                   l.nome_localidade
            FROM associacao a
            LEFT JOIN localidade l ON a.id_localidade = l.id_localidade
            WHERE a.id_associacao = %s
        """, [request.user.id_associacao])
        associacao = cursor.fetchone()

    return render(request, 'associacao/portal/associacao.html', {'associacao': associacao})


@associado_required
def portal_minhas_quotas(request):
    """
    Quotas e pagamentos do associado logado.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                qa.id_quota_associado,
                q.designacao_quota,
                q.valor_quota,
                q.periodicidade_quota,
                qa.valor_devido,
                qa.data_vencimento,
                qa.periodo_referencia,
                qa.estado_quota_associado,
                q.id_quota
            FROM quota_associado qa
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE qa.id_associado = %s
            ORDER BY qa.data_vencimento DESC
        """, [request.user.id_associado])
        quotas = cursor.fetchall()

        # Pagamentos do associado
        cursor.execute("""
            SELECT
                p.id_pagamento,
                p.data_pagamento,
                p.valor_pago,
                p.metodo_pagamento,
                p.referencia_pagamento,
                q.designacao_quota,
                qa.periodo_referencia
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE qa.id_associado = %s
            ORDER BY p.data_pagamento DESC
        """, [request.user.id_associado])
        pagamentos = cursor.fetchall()

    return render(request, 'associacao/portal/minhas_quotas.html', {
        'quotas': quotas,
        'pagamentos': pagamentos,
    })


@associado_required
def portal_perfil(request):
    """Consulta e edição dos dados pessoais globais do associado."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                a.id_associado, a.numero_associado, a.nome, a.nif,
                a.data_nascimento, a.email, a.telefone,
                a.data_adesao, a.data_saida, a.estado,
                a.tipo_via, a.nome_via, a.numero_porta, a.andar,
                a.codigo_postal, a.id_localidade, l.nome_localidade, a.password_hash
            FROM associado a
            LEFT JOIN localidade l ON a.id_localidade = l.id_localidade
            WHERE a.id_associado = %s
        """, [request.user.id_associado])
        associado = cursor.fetchone()

    if not associado:
        messages.error(request, 'Não foi possível encontrar o seu perfil.')
        return redirect('dashboard_associado')

    if request.method == 'POST':
        form = PerfilAssociadoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            nova_password = dados['nova_palavra_passe']
            if nova_password and not check_password(dados['palavra_passe_atual'], associado[17]):
                form.add_error('palavra_passe_atual', 'A palavra-passe atual está incorreta.')
            else:
                # O NIF anterior identifica todas as inscrições da mesma pessoa.
                # Número de associado, adesão e estado são próprios de cada associação.
                password_hash = make_password(nova_password) if nova_password else None
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE associado
                            SET nome = %s, data_nascimento = %s, email = %s,
                                telefone = %s, tipo_via = %s, nome_via = %s,
                                numero_porta = %s, andar = %s, codigo_postal = %s,
                                id_localidade = %s,
                                password_hash = COALESCE(%s, password_hash)
                            WHERE nif = %s
                        """, [
                            dados['nome'], dados['data_nascimento'], dados['email'],
                            dados['telefone'], dados['tipo_via'], dados['nome_via'],
                            dados['numero_porta'], dados['andar'], dados['codigo_postal'],
                            dados['id_localidade'], password_hash, associado[3],
                        ])
                        total_atualizados = cursor.rowcount

                if not form.errors:
                    request.user.nome = dados['nome']
                    if password_hash:
                        request.user.password_hash = password_hash
                        update_session_auth_hash(request, request.user)
                    campos_perfil = [
                        'nome', 'data_nascimento', 'email', 'telefone', 'morada',
                    ]
                    registar_auditoria(request, 'update', 'associado', request.user.id_associado, {
                        'campos_atualizados': campos_perfil,
                        'inscricoes_atualizadas': total_atualizados,
                    })
                    if password_hash:
                        registar_auditoria(request, 'credentials_changed', 'associado', request.user.id_associado, {
                            'inscricoes_atualizadas': total_atualizados,
                        })
                    messages.success(
                        request,
                        f'Perfil atualizado em {total_atualizados} associação(ões).',
                    )
                    return redirect('portal_perfil')
    else:
        form = PerfilAssociadoForm(initial={
            'nome': associado[2], 'data_nascimento': associado[4],
            'email': associado[5], 'telefone': associado[6], 'tipo_via': associado[10],
            'nome_via': associado[11], 'numero_porta': associado[12], 'andar': associado[13],
            'codigo_postal': associado[14], 'id_localidade': associado[15],
            'localidade': associado[16],
        })

    return render(request, 'associacao/portal/perfil.html', {
        'associado': associado,
        'form': form,
        'editing': request.GET.get('editar') == '1' or (request.method == 'POST' and form.errors),
    })


# ==========================================
# MOVIMENTOS BANCÁRIOS
# ==========================================

@direcao_required
def listar_movimentos_bancarios(request):
    movimentos = database.listar_movimentos_bancarios(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_movimentos_bancarios.html',
        {'movimentos': movimentos}
    )


@direcao_required
@direcao_required
def registar_movimento_bancario(request):
    if request.method == 'POST':
        form = MovimentoBancarioForm(request.POST)

        if form.is_valid():
            database.inserir_movimento_bancario(
                form.cleaned_data['data_movimento'],
                form.cleaned_data['descricao_movimento'],
                form.cleaned_data['valor_movimento'],
                form.cleaned_data['referencia_movimento'],
                request.user.id_associacao
            )
            registar_auditoria(request, 'create', 'movimento_bancario', details={'referencia': form.cleaned_data['referencia_movimento']})

            messages.success(request, 'Movimento bancário registado com sucesso.')
            return redirect('listar_movimentos_bancarios')

    else:
        form = MovimentoBancarioForm()

    return render(
        request,
        'associacao/registar_movimento_bancario.html',
        {'form': form}
    )


@direcao_required
def editar_movimento_bancario(request, id_movimento):
    movimento = database.obter_movimento_bancario(id_movimento)

    if not movimento:
        messages.error(request, 'Movimento bancário não encontrado.')
        return redirect('listar_movimentos_bancarios')

    # Verificar se o movimento pertence à associação autenticada
    # vw_movimentos_bancarios tem id_associacao no final (pode ser NULL)
    movimento_associacao = movimento[-1] if len(movimento) > 5 else None
    if movimento_associacao != request.user.id_associacao:
        messages.error(request, 'Movimento bancário não encontrado.')
        return redirect('listar_movimentos_bancarios')

    if request.method == 'POST':
        form = MovimentoBancarioForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_movimento_bancario(
                id_movimento,
                dados['data_movimento'], dados['descricao_movimento'],
                dados['valor_movimento'], dados['referencia_movimento'],
                request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'movimento_bancario', id_movimento)
            messages.success(request, 'Movimento bancário atualizado com sucesso.')
            return redirect('listar_movimentos_bancarios')
    else:
        form = MovimentoBancarioForm(initial={
            'data_movimento': movimento[1],
            'descricao_movimento': movimento[2],
            'valor_movimento': movimento[3],
            'referencia_movimento': movimento[4],
        })

    return render(request, 'associacao/editar_movimento_bancario.html', {'form': form, 'editar': True, 'id': id_movimento})


@direcao_required
def eliminar_movimento_bancario(request, id_movimento):
    if request.method == 'POST':
        # Verificar se o movimento pertence à associação autenticada
        movimento = database.obter_movimento_bancario(id_movimento)
        if movimento and len(movimento) > 5 and movimento[-1] == request.user.id_associacao:
            database.eliminar_movimento_bancario(id_movimento, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'movimento_bancario', id_movimento)
            messages.success(request, 'Movimento bancário eliminado com sucesso.')
        else:
            messages.error(request, 'Movimento bancário não encontrado.')
    return redirect('listar_movimentos_bancarios')


# ==========================================
# PAGAMENTOS
# ==========================================

@direcao_required
def listar_pagamentos(request):
    pagamentos = database.listar_pagamentos(request.user.id_associacao)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(p.valor_pago), 0), COUNT(*), COUNT(DISTINCT p.id_quota_associado)
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE q.id_associacao = %s
        """, [request.user.id_associacao])
        total_recebido, total_pagamentos, total_quotas_pagas = cursor.fetchone()
        cursor.execute("""
            SELECT p.metodo_pagamento, COUNT(*)
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE q.id_associacao = %s
            GROUP BY p.metodo_pagamento
            ORDER BY COUNT(*) DESC, p.metodo_pagamento
            LIMIT 1
        """, [request.user.id_associacao])
        metodo = cursor.fetchone()
        cursor.execute("""
            SELECT p.data_pagamento, a.nome
            FROM pagamento p
            JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
            JOIN associado a ON qa.id_associado = a.id_associado
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE q.id_associacao = %s
            ORDER BY p.data_pagamento DESC, p.id_pagamento DESC
            LIMIT 1
        """, [request.user.id_associacao])
        ultimo_pagamento = cursor.fetchone()

    return render(
        request,
        'associacao/listar_pagamentos.html',
        {
            'pagamentos': pagamentos,
            'total_recebido': total_recebido,
            'total_pagamentos': total_pagamentos,
            'total_quotas_pagas': total_quotas_pagas,
            'metodo_mais_usado': metodo[0] if metodo else '—',
            'perc_metodo_mais_usado': round((metodo[1] / total_pagamentos) * 100) if metodo else 0,
            'ultimo_pagamento_data': ultimo_pagamento[0] if ultimo_pagamento else None,
            'ultimo_pagamento_associado': ultimo_pagamento[1] if ultimo_pagamento else '—',
        }
    )


@direcao_required
def registar_pagamento(request):
    if request.method == 'POST':
        form = PagamentoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            id_movimento = int(dados['id_movimento']) if dados['id_movimento'] else None
            database.inserir_pagamento(
                dados['data_pagamento'],
                dados['valor_pago'],
                dados['metodo_pagamento'],
                dados['referencia_pagamento'],
                int(dados['id_quota_associado']),
                id_movimento,
                request.user.id_associacao
            )
            registar_auditoria(request, 'create', 'pagamento', details={'id_quota_associado': int(dados['id_quota_associado'])})

            messages.success(request, 'Pagamento registado com sucesso.')
            return redirect('listar_pagamentos')

    else:
        form = PagamentoForm()

    return render(
        request,
        'associacao/registar_pagamento.html',
        {'form': form}
    )


@direcao_required
def editar_pagamento(request, id_pagamento):
    pagamento = database.obter_pagamento(id_pagamento)

    if not pagamento:
        messages.error(request, 'Pagamento não encontrado.')
        return redirect('listar_pagamentos')

    # Verificar se o pagamento pertence à associação autenticada
    # vw_pagamentos tem id_associacao no final
    pagamento_associacao = pagamento[-1] if len(pagamento) > 25 else None
    if pagamento_associacao != request.user.id_associacao:
        messages.error(request, 'Pagamento não encontrado.')
        return redirect('listar_pagamentos')

    if request.method == 'POST':
        form = PagamentoForm(request.POST, id_associacao=request.user.id_associacao)

        if form.is_valid():
            dados = form.cleaned_data
            id_movimento = int(dados['id_movimento']) if dados['id_movimento'] else None
            database.atualizar_pagamento(
                id_pagamento,
                dados['data_pagamento'],
                dados['valor_pago'],
                dados['metodo_pagamento'],
                dados['referencia_pagamento'],
                int(dados['id_quota_associado']),
                id_movimento,
                request.user.id_associacao
            )
            registar_auditoria(request, 'update', 'pagamento', id_pagamento)
            messages.success(request, 'Pagamento atualizado com sucesso.')
            return redirect('listar_pagamentos')
    else:
        form = PagamentoForm(initial={
            'data_pagamento': pagamento[1],
            'valor_pago': pagamento[2],
            'metodo_pagamento': pagamento[3],
            'referencia_pagamento': pagamento[4],
            'id_quota_associado': str(pagamento[5]),
            'id_movimento': str(pagamento[14]) if pagamento[14] else '',
        }, id_associacao=request.user.id_associacao)

    return render(request, 'associacao/editar_pagamento.html', {'form': form, 'editar': True, 'id': id_pagamento})


@direcao_required
def eliminar_pagamento(request, id_pagamento):
    if request.method == 'POST':
        # Verificar se o pagamento pertence à associação autenticada
        pagamento = database.obter_pagamento(id_pagamento)
        if pagamento and len(pagamento) > 25 and pagamento[-1] == request.user.id_associacao:
            database.eliminar_pagamento(id_pagamento, request.user.id_associacao)
            registar_auditoria(request, 'delete', 'pagamento', id_pagamento)
            messages.success(request, 'Pagamento eliminado com sucesso.')
        else:
            messages.error(request, 'Pagamento não encontrado.')
    return redirect('listar_pagamentos')


# ==========================================
# TIPOS DE DOCUMENTO
# ==========================================

@direcao_required
def listar_tipos_documento(request):
    tipos = database.listar_tipos_documento(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_tipos_documento.html',
        {'tipos': tipos}
    )


@direcao_required
def registar_tipo_documento(request):
    if request.method == 'POST':
        form = TipoDocumentoForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    database.inserir_tipo_documento(
                        form.cleaned_data['nome_tipo_documento'],
                        form.cleaned_data['descricao_tipo_documento'],
                        request.user.id_associacao
                    )
            except IntegrityError:
                form.add_error(
                    'nome_tipo_documento',
                    'Já existe um tipo de documento com este nome nesta associação.',
                )
                return render(request, 'associacao/registar_tipo_documento.html', {'form': form})

            messages.success(request, 'Tipo de documento registado com sucesso.')
            return redirect('listar_tipos_documento')

    else:
        form = TipoDocumentoForm(initial={'id_associacao': request.user.id_associacao})

    return render(
        request,
        'associacao/registar_tipo_documento.html',
        {'form': form}
    )


@direcao_required
def editar_tipo_documento(request, id_tipo_documento):
    tipo = database.obter_tipo_documento(id_tipo_documento)

    if not tipo:
        messages.error(request, 'Tipo de documento não encontrado.')
        return redirect('listar_tipos_documento')

    # Verificar se o tipo pertence à associação autenticada
    # vw_tipos_documento tem id_associacao no final
    tipo_associacao = tipo[-1] if len(tipo) > 3 else None
    if tipo_associacao != request.user.id_associacao:
        messages.error(request, 'Tipo de documento não encontrado.')
        return redirect('listar_tipos_documento')

    if request.method == 'POST':
        form = TipoDocumentoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_tipo_documento(
                id_tipo_documento,
                dados['nome_tipo_documento'],
                dados['descricao_tipo_documento'],
                request.user.id_associacao
            )
            messages.success(request, 'Tipo de documento atualizado com sucesso.')
            return redirect('listar_tipos_documento')
    else:
        form = TipoDocumentoForm(initial={
            'nome_tipo_documento': tipo[1],
            'descricao_tipo_documento': tipo[2],
            'id_associacao': request.user.id_associacao,
        })

    return render(request, 'associacao/editar_tipo_documento.html', {'form': form, 'editar': True, 'id': id_tipo_documento})


@direcao_required
def eliminar_tipo_documento(request, id_tipo_documento):
    if request.method == 'POST':
        # Verificar se o tipo pertence à associação autenticada
        tipo = database.obter_tipo_documento(id_tipo_documento)
        if tipo and len(tipo) > 3 and tipo[-1] == request.user.id_associacao:
            database.eliminar_tipo_documento(id_tipo_documento, request.user.id_associacao)
            messages.success(request, 'Tipo de documento eliminado com sucesso.')
        else:
            messages.error(request, 'Tipo de documento não encontrado.')
    return redirect('listar_tipos_documento')


# ==========================================
# DOCUMENTOS
# ==========================================

@direcao_required
def listar_documentos(request):
    documentos = database.listar_documentos(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_documentos.html',
        {'documentos': documentos}
    )


@direcao_required
def registar_documento(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, id_associacao=request.user.id_associacao)

        if form.is_valid():
            dados = form.cleaned_data
            id_mandato = int(dados['id_mandato']) if dados['id_mandato'] else None

            # Validar que tipo_documento e mandato pertencem à mesma associação
            from django.db import connection
            with connection.cursor() as cursor:
                # Verificar tipo_documento
                cursor.execute("SELECT id_associacao FROM tipo_documento WHERE id_tipo_documento = %s", [int(dados['id_tipo_documento'])])
                tipo_row = cursor.fetchone()
                if not tipo_row or tipo_row[0] != request.user.id_associacao:
                    form.add_error('id_tipo_documento', 'Tipo de documento não pertence a esta associação.')
                    return render(request, 'associacao/registar_documento.html', {'form': form})

                # Verificar mandato se fornecido
                if id_mandato:
                    cursor.execute("SELECT id_associacao FROM mandato WHERE id_mandato = %s", [id_mandato])
                    mandato_row = cursor.fetchone()
                    if not mandato_row or mandato_row[0] != request.user.id_associacao:
                        form.add_error('id_mandato', 'Mandato não pertence a esta associação.')
                        return render(request, 'associacao/registar_documento.html', {'form': form})

            # Guardar ficheiro no sistema de ficheiros
            ficheiro = dados['ficheiro']
            caminho_ficheiro = database.guardar_ficheiro_documento(ficheiro, request.user.id_associacao)

            database.inserir_documento(
                dados['nome_documento'],
                dados['data_upload'],
                dados['data_documento'],
                caminho_ficheiro,
                dados['observacoes'],
                int(dados['id_tipo_documento']),
                request.user.id_associacao,
                id_mandato
            )

            # Auditoria: registar criação de documento
            registar_auditoria(request, 'create', 'documento', details={
                    'nome_documento': dados['nome_documento'],
                    'id_tipo_documento': int(dados['id_tipo_documento']),
                    'id_mandato': id_mandato,
                    'nome_ficheiro_original': ficheiro.name,
                    'tamanho_ficheiro': ficheiro.size,
                })

            messages.success(request, 'Documento registado com sucesso.')
            return redirect('listar_documentos')

    else:
        form = DocumentoForm(initial={'id_associacao': request.user.id_associacao}, id_associacao=request.user.id_associacao)

    return render(
        request,
        'associacao/registar_documento.html',
        {'form': form}
    )


@direcao_required
def editar_documento(request, id_documento):
    documento = database.obter_documento(id_documento)

    if not documento:
        messages.error(request, 'Documento não encontrado.')
        return redirect('listar_documentos')

    # Verificar se o documento pertence à associação autenticada
    # vw_documentos tem id_associacao no final (posição 12)
    documento_associacao = documento[-1] if len(documento) > 12 else None
    if documento_associacao != request.user.id_associacao:
        messages.error(request, 'Documento não encontrado.')
        return redirect('listar_documentos')

    # Guardar dados originais para auditoria
    ficheiro_antigo = documento[4] if len(documento) > 4 else None

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, id_associacao=request.user.id_associacao, editing=True)

        if form.is_valid():
            dados = form.cleaned_data
            id_mandato = int(dados['id_mandato']) if dados['id_mandato'] else None

            # Verificar se foi carregado um novo ficheiro
            novo_ficheiro = dados['ficheiro']
            caminho_ficheiro = ficheiro_antigo

            if novo_ficheiro and hasattr(novo_ficheiro, 'name'):
                # Guardar novo ficheiro
                caminho_ficheiro = database.guardar_ficheiro_documento(novo_ficheiro, request.user.id_associacao)
                # Eliminar ficheiro antigo
                if ficheiro_antigo:
                    database.eliminar_ficheiro_documento(ficheiro_antigo)

            database.atualizar_documento(
                id_documento,
                dados['nome_documento'],
                dados['data_upload'],
                dados['data_documento'],
                caminho_ficheiro,
                dados['observacoes'],
                int(dados['id_tipo_documento']),
                request.user.id_associacao,
                id_mandato
            )

            # Auditoria: registar atualização de documento
            detalhes = {
                'nome_documento': dados['nome_documento'],
                'id_tipo_documento': int(dados['id_tipo_documento']),
                'id_mandato': id_mandato,
            }
            if novo_ficheiro and hasattr(novo_ficheiro, 'name'):
                detalhes['ficheiro_substituido'] = True
                detalhes['nome_ficheiro_novo'] = novo_ficheiro.name
                detalhes['tamanho_ficheiro_novo'] = novo_ficheiro.size

            registar_auditoria(request, 'update', 'documento', id_documento, detalhes)

            messages.success(request, 'Documento atualizado com sucesso.')
            return redirect('listar_documentos')
    else:
        form = DocumentoForm(initial={
            'nome_documento': documento[1],
            'data_upload': documento[2],
            'data_documento': documento[3],
            'ficheiro': documento[4],  # Caminho do ficheiro
            'observacoes': documento[5],
            'id_tipo_documento': str(documento[6]),
            'id_associacao': request.user.id_associacao,
            'id_mandato': str(documento[11]) if documento[11] else '',
        }, id_associacao=request.user.id_associacao)

    return render(request, 'associacao/editar_documento.html', {'form': form, 'editar': True, 'id': id_documento, 'documento': documento})


@direcao_required
def eliminar_documento(request, id_documento):
    if request.method == 'POST':
        # Verificar se o documento pertence à associação autenticada
        documento = database.obter_documento(id_documento)
        if documento and len(documento) > 12 and documento[-1] == request.user.id_associacao:
            ficheiro = documento[4] if len(documento) > 4 else None
            database.eliminar_documento(id_documento, request.user.id_associacao)

            # Eliminar ficheiro físico
            if ficheiro:
                database.eliminar_ficheiro_documento(ficheiro)

            # Auditoria: registar eliminação de documento
            registar_auditoria(request, 'delete', 'documento', id_documento, {
                    'nome_documento': documento[1] if len(documento) > 1 else '',
                    'nome_ficheiro': ficheiro,
                })

            messages.success(request, 'Documento eliminado com sucesso.')
        else:
            messages.error(request, 'Documento não encontrado.')
    return redirect('listar_documentos')


@direcao_required
def descarregar_documento(request, id_documento):
    """
    Download seguro de documento com verificação de permissões.
    """
    from django.http import FileResponse, Http404
    import os

    documento = database.obter_documento(id_documento)

    if not documento:
        messages.error(request, 'Documento não encontrado.')
        return redirect('listar_documentos')

    # Verificar se o documento pertence à associação autenticada
    documento_associacao = documento[-1] if len(documento) > 12 else None
    if documento_associacao != request.user.id_associacao:
        messages.error(request, 'Documento não encontrado.')
        return redirect('listar_documentos')

    # Obter caminho do ficheiro (posição 4 no vw_documentos)
    caminho_relativo = documento[4] if len(documento) > 4 else None

    if not caminho_relativo:
        messages.error(request, 'Ficheiro não disponível.')
        return redirect('listar_documentos')

    caminho_completo = database.obter_caminho_ficheiro_documento(caminho_relativo)

    if not os.path.exists(caminho_completo):
        messages.error(request, 'Ficheiro não encontrado no servidor.')
        return redirect('listar_documentos')

    registar_auditoria(request, 'download', 'documento', id_documento, {
        'nome_documento': documento[1] if len(documento) > 1 else '',
        'nome_ficheiro': os.path.basename(caminho_relativo),
    })

    # Determinar nome do ficheiro para download
    nome_download = documento[1] if len(documento) > 1 else 'documento'
    ext = os.path.splitext(caminho_relativo)[1]
    if ext:
        nome_download += ext

    response = FileResponse(open(caminho_completo, 'rb'), as_attachment=True, filename=nome_download)
    return response


@direcao_required
def estatisticas(request):
    id_associacao = request.user.id_associacao
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE estado = 'Ativo' AND (data_saida IS NULL OR data_saida > CURRENT_DATE)),
                   COUNT(*) FILTER (WHERE estado <> 'Ativo' OR (data_saida IS NOT NULL AND data_saida <= CURRENT_DATE))
            FROM associado WHERE id_associacao = %s
        """, [id_associacao])
        total_associados, associados_ativos, associados_inativos = cursor.fetchone()
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE estado_quota_associado = 'Paga'),
                COUNT(*) FILTER (WHERE estado_quota_associado = 'Pendente'),
                COUNT(*) FILTER (WHERE estado_quota_associado IN ('Em Dívida', 'Parcial'))
            FROM quota_associado qa
            JOIN quota q ON q.id_quota = qa.id_quota
            WHERE q.id_associacao = %s
        """, [id_associacao])
        quotas_pagas, quotas_pendentes, quotas_divida = cursor.fetchone()
        cursor.execute("""
            SELECT COALESCE(SUM(p.valor_pago), 0)
            FROM pagamento p
            JOIN quota_associado qa ON qa.id_quota_associado = p.id_quota_associado
            JOIN quota q ON q.id_quota = qa.id_quota
            WHERE q.id_associacao = %s
        """, [id_associacao])
        total_pagamentos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM vw_movimentos_nao_conciliados WHERE id_associacao = %s", [id_associacao])
        movimentos_por_conciliar = cursor.fetchone()[0]
        cursor.execute("""
            SELECT DATE_TRUNC('month', p.data_pagamento)::date, COALESCE(SUM(p.valor_pago), 0)
            FROM pagamento p
            JOIN quota_associado qa ON qa.id_quota_associado = p.id_quota_associado
            JOIN quota q ON q.id_quota = qa.id_quota
            WHERE q.id_associacao = %s
            GROUP BY DATE_TRUNC('month', p.data_pagamento)
            ORDER BY DATE_TRUNC('month', p.data_pagamento)
        """, [id_associacao])
        pagamentos_mensais = [{'mes': mes, 'total': total} for mes, total in cursor.fetchall()]
    return render(request, 'associacao/estatisticas.html', {
        'total_associados': total_associados,
        'associados_ativos': associados_ativos,
        'associados_inativos': associados_inativos,
        'quotas_pagas': quotas_pagas,
        'quotas_pendentes': quotas_pendentes,
        'quotas_divida': quotas_divida,
        'total_pagamentos': total_pagamentos,
        'movimentos_por_conciliar': movimentos_por_conciliar,
        'pagamentos_mensais': pagamentos_mensais,
    })


@direcao_required
def auditoria(request):
    start_date = request.GET.get('data_inicio', '')
    end_date = request.GET.get('data_fim', '')
    action = request.GET.get('operacao', '').strip()
    entity_type = request.GET.get('entidade', '').strip()
    try:
        current_timezone = timezone.get_current_timezone()
        start = timezone.make_aware(
            datetime.combine(datetime.strptime(start_date, '%Y-%m-%d').date(), time.min),
            current_timezone,
        ).astimezone(datetime_timezone.utc).replace(tzinfo=None) if start_date else None
        end = timezone.make_aware(
            datetime.combine(datetime.strptime(end_date, '%Y-%m-%d').date(), time.max),
            current_timezone,
        ).astimezone(datetime_timezone.utc).replace(tzinfo=None) if end_date else None
    except ValueError:
        messages.error(request, 'As datas de auditoria devem estar no formato AAAA-MM-DD.')
        start = end = None
        start_date = end_date = ''

    try:
        page = max(1, int(request.GET.get('page', '1')))
    except ValueError:
        page = 1
    page_size = 100
    logs = mongodb.get_audit_logs(
        entity_type=entity_type or None, action=action or None,
        start_date=start, end_date=end, association_id=request.user.id_associacao,
        limit=page_size + 1, skip=(page - 1) * page_size,
    )
    tem_proxima = len(logs) > page_size
    logs = logs[:page_size]
    query_params = request.GET.copy()
    query_params.pop('page', None)
    url_base = request.path + ('?' + query_params.urlencode() + '&' if query_params else '?')
    ligado_mongodb = mongodb.mongodb_service.is_connected()
    return render(request, 'associacao/auditoria.html', {
        'logs': logs,
        'pagina': page,
        'tem_anterior': page > 1,
        'tem_proxima': tem_proxima,
        'url_anterior': f'{url_base}page={page - 1}',
        'url_proxima': f'{url_base}page={page + 1}',
        'ligado_mongodb': ligado_mongodb,
        'filtros': {'data_inicio': start_date, 'data_fim': end_date, 'operacao': action, 'entidade': entity_type},
    })


# ==========================================
# FASE 2.2 — IMPORTAÇÃO E CONCILIAÇÃO BANCÁRIA
# ==========================================

@direcao_required
def importar_movimentos_csv(request):
    """
    Upload e importação de arquivo CSV de movimentos bancários.
    """
    if request.method == 'POST':
        form = ImportarCSVForm(request.POST, request.FILES)
        print(f"DEBUG: Form is_valid: {form.is_valid()}")
        if not form.is_valid():
            print(f"DEBUG: Form errors: {form.errors}")

        if form.is_valid():
            arquivo = form.cleaned_data['arquivo_csv']
            delimitador = form.cleaned_data['delimitador']
            tem_cabecalho = form.cleaned_data['tem_cabecalho']
            print(f"DEBUG: arquivo={arquivo}, delimitador={delimitador}, tem_cabecalho={tem_cabecalho}")

            # Ler conteúdo do arquivo
            try:
                conteudo = arquivo.read().decode('utf-8')
            except UnicodeDecodeError:
                conteudo = arquivo.read().decode('latin-1')
            print(f"DEBUG: conteudo length={len(conteudo)}")

            # Importar via procedure
            try:
                importados, duplicados, suspeitos, erros, erros_detalhe = database.importar_movimentos_csv(
                    conteudo,
                    request.user.id_associacao,
                    delimitador,
                    tem_cabecalho
                )
                registar_auditoria(request, 'import', 'movimento_bancario', details={
                    'ficheiro': arquivo.name, 'importados': importados, 'duplicados': duplicados,
                    'suspeitos': suspeitos, 'erros': erros,
                })
                print(f"DEBUG: Import succeeded: {importados} importados, {duplicados} duplicados, {suspeitos} suspeitos, {erros} erros")

                if erros > 0:
                    msg = f'Importação concluída com {erros} erro(s): '
                    msg += '; '.join(erros_detalhe[:5])
                    if len(erros_detalhe) > 5:
                        msg += f' ... e mais {len(erros_detalhe) - 5} erro(s)'
                    messages.warning(request, msg)
                elif importados > 0:
                    msg = f'{importados} movimento(s) importado(s) com sucesso.'
                    if duplicados > 0:
                        msg += f' {duplicados} duplicado(s) ignorado(s).'
                    if suspeitos > 0:
                        msg += f' {suspeitos} movimento(s) suspeito(s) de duplicação - revisão manual recomendada.'
                    messages.success(request, msg)
                elif suspeitos > 0:
                    msg = f'{suspeitos} movimento(s) suspeito(s) de duplicação importado(s) - revisão manual recomendada.'
                    messages.warning(request, msg)
                else:
                    messages.info(request, 'Nenhum movimento novo para importar.')

                return redirect('listar_movimentos_nao_conciliados')
            except Exception as e:
                print(f"DEBUG: Import error: {e}")
                messages.error(request, f'Erro ao importar: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Erro em {field}: {error}')
    else:
        form = ImportarCSVForm()

    return render(
        request,
        'associacao/importar_movimentos_csv.html',
        {'form': form}
    )


@direcao_required
def listar_movimentos_nao_conciliados(request):
    """
    Lista movimentos bancários pendentes de conciliação.
    """
    form = FiltroMovimentosForm(request.GET)
    movimentos = database.listar_movimentos_nao_conciliados(request.user.id_associacao)

    # Aplicar filtros
    if form.is_valid():
        estado = form.cleaned_data.get('estado')
        data_inicio = form.cleaned_data.get('data_inicio')
        data_fim = form.cleaned_data.get('data_fim')
        pesquisa = form.cleaned_data.get('pesquisa')

        # Filtrar em Python (para simplicidade, já que a query é complexa)
        if estado == 'conciliado':
            # Mostrar conciliados - usar view diferente
            movimentos = database.listar_conciliacoes(request.user.id_associacao)
        elif data_inicio:
            movimentos = [m for m in movimentos if m[1] >= data_inicio]  # data_movimento
        if data_fim:
            movimentos = [m for m in movimentos if m[1] <= data_fim]
        if pesquisa:
            pesquisa_lower = pesquisa.lower()
            movimentos = [
                m for m in movimentos
                if (m[2] and pesquisa_lower in str(m[2]).lower()) or  # descricao
                   (m[4] and pesquisa_lower in str(m[4]).lower()) or  # referencia
                   (pesquisa_lower in str(m[3]).lower())  # valor
            ]

    # Obter sugestões para cada movimento pendente
    sugestoes = {}
    for movimento in movimentos:
        id_movimento = movimento[0]
        try:
            sugs = database.encontrar_correspondencias_conciliacao(id_movimento, request.user.id_associacao)
            if sugs:
                sugestoes[id_movimento] = sugs
        except Exception:
            pass

    return render(
        request,
        'associacao/listar_movimentos_nao_conciliados.html',
        {
            'movimentos': movimentos,
            'sugestoes': sugestoes,
            'form': form
        }
    )


@direcao_required
def ver_sugestoes_conciliacao(request, id_movimento):
    """
    Mostra sugestões de conciliação para um movimento específico.
    """
    # Verificar se o movimento pertence à associação do utilizador ANTES de buscar sugestões
    movimentos = database.listar_movimentos_nao_conciliados(request.user.id_associacao)
    movimento = next((m for m in movimentos if m[0] == id_movimento), None)

    if not movimento:
        # Movimento não pertence a esta associação - retornar 404
        from django.http import Http404
        raise Http404('Movimento não encontrado.')

    try:
        sugestao = database.encontrar_correspondencias_conciliacao(id_movimento, request.user.id_associacao)
    except Exception as e:
        messages.error(request, f'Erro ao buscar sugestões: {str(e)}')
        return redirect('listar_movimentos_nao_conciliados')

    return render(
        request,
        'associacao/ver_sugestoes_conciliacao.html',
        {
            'movimento': movimento,
            'sugestoes': sugestao
        }
    )


@direcao_required
def conciliar_movimento(request):
    """
    Confirma a conciliação entre um movimento e um pagamento.
    """
    if request.method == 'POST':
        form = ConciliarForm(request.POST, id_associacao=request.user.id_associacao)

        if form.is_valid():
            id_movimento = form.cleaned_data['id_movimento']
            id_pagamento = form.cleaned_data['id_pagamento']
            forcar = form.cleaned_data['forcar']

            # Verificar se o movimento pertence à associação do utilizador
            movimentos = database.listar_movimentos_nao_conciliados(request.user.id_associacao)
            movimento = next((m for m in movimentos if m[0] == id_movimento), None)
            if not movimento:
                from django.http import Http404
                raise Http404('Movimento não encontrado.')

            # Verificar se o pagamento pertence à associação
            pagamentos = database.listar_pagamentos_sem_movimento(request.user.id_associacao)
            pagamento = next((p for p in pagamentos if p[0] == id_pagamento), None)
            if not pagamento:
                from django.http import Http404
                raise Http404('Pagamento não encontrado.')

            try:
                database.conciliar_movimento_pagamento(
                    id_movimento,
                    id_pagamento,
                    request.user.id_associacao,
                    forcar
                )
                registar_auditoria(request, 'reconcile', 'movimento_bancario', id_movimento, {'id_pagamento': id_pagamento, 'forcar': forcar})
                messages.success(request, 'Conciliação realizada com sucesso.')
                return redirect('listar_movimentos_nao_conciliados')
            except Exception as e:
                # Correspondência ambígua - já tratada na função (retorna False)
                if 'Correspondência ambígua' in str(e):
                    messages.error(request, f'Erro na conciliação: {str(e)}')
                    return redirect('listar_movimentos_nao_conciliados')
                raise
        else:
            # Formulário inválido
            from django.http import Http404
            raise Http404('Movimento ou pagamento não encontrado.')

    return redirect('listar_movimentos_nao_conciliados')


@direcao_required
def desfazer_conciliacao_view(request):
    """
    Desfaz a conciliação entre um movimento e um pagamento.
    """
    if request.method == 'POST':
        form = DesfazerConciliacaoForm(request.POST, id_associacao=request.user.id_associacao)

        if form.is_valid():
            id_conciliacao = form.cleaned_data['id_conciliacao']
            motivo = form.cleaned_data.get('motivo', 'Reversão manual')

            try:
                database.desfazer_conciliacao(
                    id_associacao=request.user.id_associacao,
                    id_conciliacao=id_conciliacao,
                    motivo=motivo,
                    utilizador=request.user.username if hasattr(request.user, 'username') else 'direcao'
                )
                registar_auditoria(request, 'unreconcile', 'conciliacao_bancaria', id_conciliacao, {'motivo': motivo})
                messages.success(request, 'Conciliação desfeita com sucesso.')
            except Exception as e:
                messages.error(request, f'Erro ao desfazer conciliação: {str(e)}')

    return redirect('listar_movimentos_nao_conciliados')


@direcao_required
def historico_conciliacoes(request):
    """
    Histórico de conciliações realizadas.
    """
    conciliacoes = database.listar_conciliacoes(request.user.id_associacao)

    return render(
        request,
        'associacao/historico_conciliacoes.html',
        {'conciliacoes': conciliacoes}
    )


@direcao_required
def listar_movimentos_suspeitos(request):
    """
    Lista movimentos bancários suspeitos de duplicação para revisão manual.
    """
    suspeitos = database.listar_movimentos_suspeitos(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_movimentos_suspeitos.html',
        {'suspeitos': suspeitos}
    )
