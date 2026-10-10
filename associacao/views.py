from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password

from . import database
from .forms import (
    MandatoForm,
    ExercicioCargoForm,
    AssociacaoForm,
    EventoForm,
    AssociadoForm,
    QuotaForm,
    OrgaoSocialForm,
    CargoForm
)


def registar_mandato(request):
    if request.method == 'POST':
        form = MandatoForm(request.POST)

        if form.is_valid():
            database.inserir_mandato(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                form.cleaned_data['id_associacao']
            )

            return redirect('listar_mandatos')

    else:
        form = MandatoForm()

    return render(
        request,
        'associacao/registar_mandato.html',
        {'form': form}
    )


def listar_mandatos(request):
    mandatos = database.listar_mandatos()

    return render(
        request,
        'associacao/listar_mandatos.html',
        {'mandatos': mandatos}
    )


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


def listar_exercicios_cargo(request):
    exercicios = database.listar_exercicios_cargo()

    return render(
        request,
        'associacao/listar_exercicios_cargo.html',
        {'exercicios': exercicios}
    )


# ==========================================
# ASSOCIACAO
# ==========================================

def registar_associacao(request):
    associacoes = database.listar_associacoes()

    # O sistema gere apenas uma associação.
    if associacoes:
        return redirect('listar_associacoes')

    if request.method == 'POST':
        form = AssociacaoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

            # Transformar a palavra-passe num hash seguro.
            password_hash = make_password(dados['password'])

            id_localidade = dados['id_localidade']
            if id_localidade:
                id_localidade = int(id_localidade)
            else:
                id_localidade = None

            # Confirmar novamente antes de inserir.
            if database.listar_associacoes():
                return redirect('listar_associacoes')

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
        {'form': form}
    )


def listar_associacoes(request):
    associacoes = database.listar_associacoes()

    return render(
        request,
        'associacao/listar_associacoes.html',
        {'associacoes': associacoes}
    )


# ==========================================
# EVENTO
# ==========================================

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


def listar_eventos(request):
    eventos = database.listar_eventos()

    return render(
        request,
        'associacao/listar_eventos.html',
        {'eventos': eventos}
    )


# ==========================================
# ASSOCIADO
# ==========================================

def registar_associado(request):
    associacoes = database.listar_associacoes_para_selecao()

    if not associacoes:
        return redirect("listar_associacoes")

    id_associacao = associacoes[0][0]

    if request.method == "POST":
        form = AssociadoForm(request.POST)

        if form.is_valid():
            dados = form.cleaned_data

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

            return redirect("listar_associados")

    else:
        form = AssociadoForm()

    return render(
        request,
        "associacao/registar_associado.html",
        {"form": form}
    )


def listar_associados(request):
    associados = database.listar_associados_completos()

    return render(
        request,
        "associacao/listar_associados.html",
        {"associados": associados}
    )


# ==========================================
# QUOTA
# ==========================================

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


def listar_quotas(request):
    quotas = database.listar_quotas()

    return render(
        request,
        "associacao/listar_quotas.html",
        {"quotas": quotas}
    )


# ==========================================
# ÓRGÃO SOCIAL
# ==========================================

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


def listar_orgaos_sociais(request):
    orgaos = database.listar_orgaos_sociais()

    return render(
        request,
        "associacao/listar_orgaos_sociais.html",
        {"orgaos": orgaos}
    )


# ==========================================
# CARGO
# ==========================================

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


def listar_cargos(request):
    cargos = database.listar_cargos_completos()

    return render(
        request,
        "associacao/listar_cargos.html",
        {"cargos": cargos}
    )
