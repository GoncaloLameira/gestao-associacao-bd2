from django.urls import path
from . import views

urlpatterns = [
    # ==========================================
    # MANDATOS
    # ==========================================

    path(
        'mandatos/',
        views.listar_mandatos,
        name='listar_mandatos'
    ),
    path(
        'mandatos/novo/',
        views.registar_mandato,
        name='registar_mandato'
    ),

    # ==========================================
    # EXERCICIOS DE CARGO
    # ==========================================

    path(
        'exercicios-cargo/',
        views.listar_exercicios_cargo,
        name='listar_exercicios_cargo'
    ),
    path(
        'exercicios-cargo/novo/',
        views.registar_exercicio_cargo,
        name='registar_exercicio_cargo'
    ),

    # ==========================================
    # ASSOCIACAO
    # ==========================================

    path(
        'associacoes/',
        views.listar_associacoes,
        name='listar_associacoes'
    ),
    path(
        'associacoes/novo/',
        views.registar_associacao,
        name='registar_associacao'
    ),

    # ==========================================
    # EVENTOS
    # ==========================================

    path(
        'eventos/',
        views.listar_eventos,
        name='listar_eventos'
    ),
    path(
        'eventos/novo/',
        views.registar_evento,
        name='registar_evento'
    ),

    path("associados/", views.listar_associados, name="listar_associados"),
    path("associados/novo/", views.registar_associado, name="registar_associado"),

    path("quotas/", views.listar_quotas, name="listar_quotas"),
    path("quotas/novo/", views.registar_quota, name="registar_quota"),


    # Órgãos Sociais
    path(
        "orgaos-sociais/",
        views.listar_orgaos_sociais,
        name="listar_orgaos_sociais"
    ),
    path(
        "orgaos-sociais/novo/",
        views.registar_orgao_social,
        name="registar_orgao_social"
    ),

    # Cargos
    path(
        "cargos/",
        views.listar_cargos,
        name="listar_cargos"
    ),
    path(
        "cargos/novo/",
        views.registar_cargo,
        name="registar_cargo"
    ),

]
