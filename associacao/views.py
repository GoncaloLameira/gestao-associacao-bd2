from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

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
    DocumentoForm
)
from .decorators import direcao_required, associado_required


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
            database.inserir_mandato(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                request.user.id_associacao
            )

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
                user_agent=request.META.get('HTTP_USER_AGENT')
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

    return render(
        request,
        'associacao/listar_mandatos.html',
        {'mandatos': mandatos}
    )


@direcao_required
def registar_exercicio_cargo(request):
    if request.method == 'POST':
        form = ExercicioCargoForm(request.POST)

        if form.is_valid():
            database.inserir_exercicio_cargo(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                int(form.cleaned_data['id_associado']),
                int(form.cleaned_data['id_cargo']),
                int(form.cleaned_data['id_mandato'])
)

            return redirect('listar_exercicios_cargo')

    else:
        form = ExercicioCargoForm()

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
    associacoes = database.listar_associacoes_para_selecao()

    if not associacoes:
        return redirect('listar_associacoes')

    # Utilizar a associação existente.
    id_associacao = associacoes[0][0]

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
    eventos = database.listar_eventos(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_eventos.html',
        {'eventos': eventos}
    )


# ==========================================
# ASSOCIADO
# ==========================================

@direcao_required
def registar_associado(request):
    associacoes = database.listar_associacoes_para_selecao()

    if not associacoes:
        return redirect("listar_associacoes")

    id_associacao = associacoes[0][0]

    if request.method == "POST":
        form = AssociadoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            # Handle password
            password_hash = None
            if dados['password']:
                from django.contrib.auth.hashers import make_password
                password_hash = make_password(dados['password'])

            database.inserir_associado(
                dados["numero_associado"],
                dados["nome"],
                dados["nif"],
                dados["data_nascimento"],
                dados["email"],
                dados["telefone"],
                dados["data_adesao"],
                dados["data_saida"],
                dados["estado"],
                dados["tipo_via"],
                dados["nome_via"],
                dados["numero_porta"],
                dados["andar"],
                dados["codigo_postal"],
                int(dados["id_localidade"])
                if dados["id_localidade"] else None,
                id_associacao
            )

            # Update password if provided (query by nif which is unique)
            if password_hash:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE associado SET password_hash = %s WHERE nif = %s AND id_associacao = %s",
                        [password_hash, dados["nif"], id_associacao]
                    )

            return redirect("listar_associados")

    else:
        form = AssociadoForm()

    return render(
        request,
        "associacao/registar_associado.html",
        {"form": form}
    )


@direcao_required
def listar_associados(request):
    associados = database.listar_associados_completos(request.user.id_associacao)

    return render(
        request,
        "associacao/listar_associados.html",
        {"associados": associados}
    )


# ==========================================
# QUOTA
# ==========================================

@direcao_required
def registar_quota(request):
    associacoes = database.listar_associacoes_para_selecao()

    if not associacoes:
        return redirect("listar_associacoes")

    id_associacao = associacoes[0][0]

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

    return render(
        request,
        "associacao/listar_quotas.html",
        {"quotas": quotas}
    )


# ==========================================
# ÓRGÃO SOCIAL
# ==========================================

@direcao_required
def registar_orgao_social(request):
    associacoes = database.listar_associacoes_para_selecao()

    if not associacoes:
        return redirect("listar_associacoes")

    id_associacao = associacoes[0][0]

    if request.method == "POST":
        form = OrgaoSocialForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            database.inserir_orgao_social(
                dados["nome"],
                dados["descricao"],
                id_associacao
            )

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
    orgaos = database.listar_orgaos_sociais_para_selecao()

    if not orgaos:
        return redirect("listar_orgaos_sociais")

    if request.method == "POST":
        form = CargoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            database.inserir_cargo(
                dados["nome"],
                dados["descricao"],
                int(dados["id_orgao_social"])
            )

            return redirect("listar_cargos")
    else:
        form = CargoForm()

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
            database.atualizar_mandato(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                mandato[3],  # Keep original id_associacao
                id_mandato
            )
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
        database.eliminar_mandato(id_mandato)
        messages.success(request, 'Mandato eliminado com sucesso.')
    return redirect('listar_mandatos')


# ExercicioCargo
@direcao_required
def editar_exercicio_cargo(request, id_exercicio_cargo):
    exercicio = database.obter_exercicio_cargo(id_exercicio_cargo)
    if not exercicio:
        messages.error(request, 'Exercício de cargo não encontrado.')
        return redirect('listar_exercicios_cargo')

    if request.method == 'POST':
        form = ExercicioCargoForm(request.POST)
        if form.is_valid():
            database.atualizar_exercicio_cargo(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                int(form.cleaned_data['id_associado']),
                int(form.cleaned_data['id_cargo']),
                int(form.cleaned_data['id_mandato']),
                id_exercicio_cargo
            )
            messages.success(request, 'Exercício de cargo atualizado com sucesso.')
            return redirect('listar_exercicios_cargo')
    else:
        form = ExercicioCargoForm(initial={
            'data_inicio': exercicio[1],
            'data_fim': exercicio[2],
            'id_associado': str(exercicio[3]),
            'id_cargo': str(exercicio[5]),
            'id_mandato': str(exercicio[9]),
        })

    return render(request, 'associacao/registar_exercicio_cargo.html', {'form': form, 'editar': True, 'id': id_exercicio_cargo})


@direcao_required
def eliminar_exercicio_cargo(request, id_exercicio_cargo):
    if request.method == 'POST':
        database.eliminar_exercicio_cargo(id_exercicio_cargo)
        messages.success(request, 'Exercício de cargo eliminado com sucesso.')
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
    if request.method == 'POST':
        database.eliminar_associacao(id_associacao)
        messages.success(request, 'Associação eliminada com sucesso.')
    return redirect('listar_associacoes')


# Evento
@direcao_required
def editar_evento(request, id_evento):
    evento = database.obter_evento(id_evento)
    if not evento:
        messages.error(request, 'Evento não encontrado.')
        return redirect('listar_eventos')

    associacoes = database.listar_associacoes_para_selecao()
    id_associacao = associacoes[0][0] if associacoes else None

    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_evento(
                id_evento,
                dados['nome_evento'], dados['descricao_evento'],
                dados['data_inicio_evento'], dados['data_fim_evento'],
                dados['local_evento'], dados['estado_evento'], id_associacao
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
        database.eliminar_evento(id_evento)
        messages.success(request, 'Evento eliminado com sucesso.')
    return redirect('listar_eventos')


# Associado
@direcao_required
def editar_associado(request, id_associado):
    associado = database.obter_associado(id_associado)
    if not associado:
        messages.error(request, 'Associado não encontrado.')
        return redirect('listar_associados')

    associacoes = database.listar_associacoes_para_selecao()
    id_associacao = associacoes[0][0] if associacoes else None

    if request.method == 'POST':
        form = AssociadoForm(request.POST)
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
                id_associacao
            )

            # Update password if provided
            if password_hash:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE associado SET password_hash = %s WHERE id_associado = %s",
                        [password_hash, id_associado]
                    )

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
        })
        # Adicionar o nome da localidade ao form para o template
        form.localidade_nome = localidade_nome

    return render(request, 'associacao/registar_associado.html', {'form': form, 'editar': True, 'id': id_associado})


@direcao_required
def eliminar_associado(request, id_associado):
    if request.method == 'POST':
        database.eliminar_associado(id_associado)
        messages.success(request, 'Associado eliminado com sucesso.')
    return redirect('listar_associados')


# Quota
@direcao_required
def editar_quota(request, id_quota):
    quota = database.obter_quota(id_quota)
    if not quota:
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
                dados['data_fim_quota'], quota[6]  # id_associacao
            )
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
        database.eliminar_quota(id_quota)
        messages.success(request, 'Quota eliminada com sucesso.')
    return redirect('listar_quotas')


# OrgaoSocial
@direcao_required
def editar_orgao_social(request, id_orgao_social):
    orgao = database.obter_orgao_social(id_orgao_social)
    if not orgao:
        messages.error(request, 'Órgão social não encontrado.')
        return redirect('listar_orgaos_sociais')

    if request.method == 'POST':
        form = OrgaoSocialForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_orgao_social(
                id_orgao_social, dados['nome'], dados['descricao'], orgao[3]
            )
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
        database.eliminar_orgao_social(id_orgao_social)
        messages.success(request, 'Órgão social eliminado com sucesso.')
    return redirect('listar_orgaos_sociais')


# Cargo
@direcao_required
def editar_cargo(request, id_cargo):
    cargo = database.obter_cargo(id_cargo)
    if not cargo:
        messages.error(request, 'Cargo não encontrado.')
        return redirect('listar_cargos')

    if request.method == 'POST':
        form = CargoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_cargo(
                id_cargo, dados['nome'], dados['descricao'], int(dados['id_orgao_social'])
            )
            messages.success(request, 'Cargo atualizado com sucesso.')
            return redirect('listar_cargos')
    else:
        form = CargoForm(initial={
            'nome': cargo[1],
            'descricao': cargo[2],
            'id_orgao_social': str(cargo[3]),
        })

    return render(request, 'associacao/registar_cargo.html', {'form': form, 'editar': True, 'id': id_cargo})


@direcao_required
def eliminar_cargo(request, id_cargo):
    if request.method == 'POST':
        database.eliminar_cargo(id_cargo)
        messages.success(request, 'Cargo eliminado com sucesso.')
    return redirect('listar_cargos')


# QuotaAssociado
@direcao_required
def listar_quotas_associado(request):
    quotas = database.listar_quotas_associado()
    return render(request, 'associacao/listar_quotas_associado.html', {'quotas': quotas})


@direcao_required
def gerar_quotas_associados_view(request):
    if request.method == 'POST':
        from .forms import GerarQuotasForm
        form = GerarQuotasForm(request.POST)
        if form.is_valid():
            database.gerar_quotas_associados(
                int(form.cleaned_data['id_quota']),
                form.cleaned_data['data_vencimento_inicial'],
                form.cleaned_data['periodos']
            )
            messages.success(request, 'Quotas geradas com sucesso para todos os associados ativos.')
            return redirect('listar_quotas_associado')
    else:
        from .forms import GerarQuotasForm
        form = GerarQuotasForm()

    return render(request, 'associacao/gerar_quotas_associados.html', {'form': form})


@direcao_required
def editar_quota_associado(request, id_quota_associado):
    quota_assoc = database.obter_quota_associado(id_quota_associado)
    if not quota_assoc:
        messages.error(request, 'Quota do associado não encontrada.')
        return redirect('listar_quotas_associado')

    if request.method == 'POST':
        from .forms import QuotaAssociadoForm
        form = QuotaAssociadoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_quota_associado(
                id_quota_associado,
                dados['valor_devido'], dados['data_vencimento'],
                dados['periodo_referencia'], dados['estado_quota_associado'],
                int(dados['id_associado']), int(dados['id_quota'])
            )
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
        })

    return render(request, 'associacao/editar_quota_associado.html', {'form': form, 'editar': True, 'id': id_quota_associado})


@direcao_required
def eliminar_quota_associado(request, id_quota_associado):
    if request.method == 'POST':
        database.eliminar_quota_associado(id_quota_associado)
        messages.success(request, 'Quota do associado eliminada com sucesso.')
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
            SELECT COUNT(*), COALESCE(SUM(valor_devido), 0)
            FROM quota_associado qa
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida')
            AND q.id_associacao = %s
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
        'quotas_pendentes_valor': quotas_pendentes_valor,
        'total_recebido': total_recebido,
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
                COUNT(*) FILTER (WHERE qa.estado_quota_associado = 'Pago') as quotas_pagas,
                COUNT(*) FILTER (WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida')) as quotas_pendentes,
                COALESCE(SUM(qa.valor_devido) FILTER (WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida')), 0) as valor_pendente
            FROM quota_associado qa
            JOIN quota q ON qa.id_quota = q.id_quota
            WHERE qa.id_associado = %s
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
        'proximos_eventos': proximos_eventos,
        'quotas_resumo': {
            'total': quotas_resumo[0] if quotas_resumo else 0,
            'pagas': quotas_resumo[1] if quotas_resumo else 0,
            'pendentes': quotas_resumo[2] if quotas_resumo else 0,
            'valor_pendente': quotas_resumo[3] if quotas_resumo else 0,
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
    """
    Perfil do associado (apenas leitura).
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                a.id_associado, a.numero_associado, a.nome, a.nif,
                a.data_nascimento, a.email, a.telefone,
                a.data_adesao, a.data_saida, a.estado,
                a.tipo_via, a.nome_via, a.numero_porta, a.andar,
                a.codigo_postal, l.nome_localidade
            FROM associado a
            LEFT JOIN localidade l ON a.id_localidade = l.id_localidade
            WHERE a.id_associado = %s
        """, [request.user.id_associado])
        associado = cursor.fetchone()

    return render(request, 'associacao/portal/perfil.html', {'associado': associado})


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
def registar_movimento_bancario(request):
    if request.method == 'POST':
        form = MovimentoBancarioForm(request.POST)

        if form.is_valid():
            database.inserir_movimento_bancario(
                form.cleaned_data['data_movimento'],
                form.cleaned_data['descricao_movimento'],
                form.cleaned_data['valor_movimento'],
                form.cleaned_data['referencia_movimento']
            )

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

    if request.method == 'POST':
        form = MovimentoBancarioForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_movimento_bancario(
                id_movimento,
                dados['data_movimento'], dados['descricao_movimento'],
                dados['valor_movimento'], dados['referencia_movimento']
            )
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
        database.eliminar_movimento_bancario(id_movimento)
        messages.success(request, 'Movimento bancário eliminado com sucesso.')
    return redirect('listar_movimentos_bancarios')


# ==========================================
# PAGAMENTOS
# ==========================================

@direcao_required
def listar_pagamentos(request):
    pagamentos = database.listar_pagamentos(request.user.id_associacao)

    return render(
        request,
        'associacao/listar_pagamentos.html',
        {'pagamentos': pagamentos}
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
                id_movimento
            )

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

    if request.method == 'POST':
        form = PagamentoForm(request.POST)

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
                id_movimento
            )
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
        })

    return render(request, 'associacao/editar_pagamento.html', {'form': form, 'editar': True, 'id': id_pagamento})


@direcao_required
def eliminar_pagamento(request, id_pagamento):
    if request.method == 'POST':
        database.eliminar_pagamento(id_pagamento)
        messages.success(request, 'Pagamento eliminado com sucesso.')
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
            database.inserir_tipo_documento(
                form.cleaned_data['nome_tipo_documento'],
                form.cleaned_data['descricao_tipo_documento'],
                request.user.id_associacao
            )

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

    if request.method == 'POST':
        form = TipoDocumentoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            database.atualizar_tipo_documento(
                id_tipo_documento,
                dados['nome_tipo_documento'],
                dados['descricao_tipo_documento'],
                dados['id_associacao']
            )
            messages.success(request, 'Tipo de documento atualizado com sucesso.')
            return redirect('listar_tipos_documento')
    else:
        form = TipoDocumentoForm(initial={
            'nome_tipo_documento': tipo[1],
            'descricao_tipo_documento': tipo[2],
            'id_associacao': tipo[3],
        })

    return render(request, 'associacao/editar_tipo_documento.html', {'form': form, 'editar': True, 'id': id_tipo_documento})


@direcao_required
def eliminar_tipo_documento(request, id_tipo_documento):
    if request.method == 'POST':
        database.eliminar_tipo_documento(id_tipo_documento)
        messages.success(request, 'Tipo de documento eliminado com sucesso.')
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
        form = DocumentoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            id_mandato = int(dados['id_mandato']) if dados['id_mandato'] else None
            database.inserir_documento(
                dados['nome_documento'],
                dados['data_upload'],
                dados['data_documento'],
                dados['ficheiro'],
                dados['observacoes'],
                int(dados['id_tipo_documento']),
                dados['id_associacao'],
                id_mandato
            )

            messages.success(request, 'Documento registado com sucesso.')
            return redirect('listar_documentos')

    else:
        form = DocumentoForm(initial={'id_associacao': request.user.id_associacao})

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

    if request.method == 'POST':
        form = DocumentoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data
            id_mandato = int(dados['id_mandato']) if dados['id_mandato'] else None
            database.atualizar_documento(
                id_documento,
                dados['nome_documento'],
                dados['data_upload'],
                dados['data_documento'],
                dados['ficheiro'],
                dados['observacoes'],
                int(dados['id_tipo_documento']),
                dados['id_associacao'],
                id_mandato
            )
            messages.success(request, 'Documento atualizado com sucesso.')
            return redirect('listar_documentos')
    else:
        form = DocumentoForm(initial={
            'nome_documento': documento[1],
            'data_upload': documento[2],
            'data_documento': documento[3],
            'ficheiro': documento[4],
            'observacoes': documento[5],
            'id_tipo_documento': str(documento[6]),
            'id_associacao': request.user.id_associacao,
            'id_mandato': str(documento[11]) if documento[11] else '',
        })

    return render(request, 'associacao/editar_documento.html', {'form': form, 'editar': True, 'id': id_documento})


@direcao_required
def eliminar_documento(request, id_documento):
    if request.method == 'POST':
        database.eliminar_documento(id_documento)
        messages.success(request, 'Documento eliminado com sucesso.')
    return redirect('listar_documentos')


@direcao_required
def estatisticas(request):
    return render(request, 'associacao/estatisticas.html', {})


@direcao_required
def auditoria(request):
    return render(request, 'associacao/auditoria.html', {})
