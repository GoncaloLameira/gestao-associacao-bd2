from django.urls import path
from . import views
from . import views_auth

urlpatterns = [
    # ==========================================
    # AUTENTICAÇÃO
    # ==========================================

    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout'),

    # ==========================================
    # DASHBOARDS
    # ==========================================

    path('dashboard/direcao/', views.dashboard_direcao, name='dashboard_direcao'),
    path('dashboard/associado/', views.dashboard_associado, name='dashboard_associado'),

    # ==========================================
    # PORTAL DO ASSOCIADO
    # ==========================================

    path('portal/eventos/', views.portal_eventos, name='portal_eventos'),
    path('portal/associacao/', views.portal_associacao, name='portal_associacao'),
    path('portal/minhas-quotas/', views.portal_minhas_quotas, name='portal_minhas_quotas'),
    path('portal/perfil/', views.portal_perfil, name='portal_perfil'),

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
    path(
        'mandatos/<int:id_mandato>/editar/',
        views.editar_mandato,
        name='editar_mandato'
    ),
    path(
        'mandatos/<int:id_mandato>/eliminar/',
        views.eliminar_mandato,
        name='eliminar_mandato'
    ),
    path('mandatos/<int:id_mandato>/', views.detalhe_mandato, name='detalhe_mandato'),
    path('passagem-posse/', views.passagem_posse, name='passagem_posse'),
    path('alterar-palavra-passe/', views.alterar_palavra_passe, name='alterar_palavra_passe'),
    path('definir-palavra-passe/', views.definir_palavra_passe_associado, name='definir_palavra_passe_associado'),

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
    path(
        'exercicios-cargo/<int:id_exercicio_cargo>/editar/',
        views.editar_exercicio_cargo,
        name='editar_exercicio_cargo'
    ),
    path(
        'exercicios-cargo/<int:id_exercicio_cargo>/eliminar/',
        views.eliminar_exercicio_cargo,
        name='eliminar_exercicio_cargo'
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
    path(
        'registar-associacao/',
        views.registar_associacao_publico,
        name='registar_associacao_publico'
    ),
    path(
        'associacoes/<int:id_associacao>/editar/',
        views.editar_associacao,
        name='editar_associacao'
    ),
    path(
        'associacoes/<int:id_associacao>/eliminar/',
        views.eliminar_associacao,
        name='eliminar_associacao'
    ),
    path(
        'api/localidade-por-codigo-postal/',
        views.localidade_por_codigo_postal,
        name='localidade_por_codigo_postal'
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
    path(
        'eventos/<int:id_evento>/editar/',
        views.editar_evento,
        name='editar_evento'
    ),
    path(
        'eventos/<int:id_evento>/eliminar/',
        views.eliminar_evento,
        name='eliminar_evento'
    ),

    # ==========================================
    # ASSOCIADOS
    # ==========================================

    path("associados/", views.listar_associados, name="listar_associados"),
    path("associados/novo/", views.registar_associado, name="registar_associado"),
    path("associados/<int:id_associado>/editar/", views.editar_associado, name="editar_associado"),
    path("associados/<int:id_associado>/eliminar/", views.eliminar_associado, name="eliminar_associado"),

    # ==========================================
    # QUOTAS
    # ==========================================

    path("quotas/", views.listar_quotas, name="listar_quotas"),
    path("quotas/novo/", views.registar_quota, name="registar_quota"),
    path("quotas/<int:id_quota>/editar/", views.editar_quota, name="editar_quota"),
    path("quotas/<int:id_quota>/eliminar/", views.eliminar_quota, name="eliminar_quota"),

    # Quota-Associado
    path("quotas-associado/", views.listar_quotas_associado, name="listar_quotas_associado"),
    path("quotas-associado/gerar/", views.gerar_quotas_associados_view, name="gerar_quotas_associados"),
    path("quotas-associado/<int:id_quota_associado>/editar/", views.editar_quota_associado, name="editar_quota_associado"),
    path("quotas-associado/<int:id_quota_associado>/eliminar/", views.eliminar_quota_associado, name="eliminar_quota_associado"),


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
    path(
        "orgaos-sociais/<int:id_orgao_social>/editar/",
        views.editar_orgao_social,
        name="editar_orgao_social"
    ),
    path(
        "orgaos-sociais/<int:id_orgao_social>/eliminar/",
        views.eliminar_orgao_social,
        name="eliminar_orgao_social"
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
    path(
        "cargos/<int:id_cargo>/editar/",
        views.editar_cargo,
        name="editar_cargo"
    ),
    path(
        "cargos/<int:id_cargo>/eliminar/",
        views.eliminar_cargo,
        name="eliminar_cargo"
    ),

    # Movimentos Bancários
    path(
        "movimentos-bancarios/",
        views.listar_movimentos_bancarios,
        name="listar_movimentos_bancarios"
    ),
    path(
        "movimentos-bancarios/novo/",
        views.registar_movimento_bancario,
        name="registar_movimento_bancario"
    ),
    path(
        "movimentos-bancarios/<int:id_movimento>/editar/",
        views.editar_movimento_bancario,
        name="editar_movimento_bancario"
    ),
    path(
        "movimentos-bancarios/<int:id_movimento>/eliminar/",
        views.eliminar_movimento_bancario,
        name="eliminar_movimento_bancario"
    ),

    # Pagamentos
    path(
        "pagamentos/",
        views.listar_pagamentos,
        name="listar_pagamentos"
    ),
    path(
        "pagamentos/novo/",
        views.registar_pagamento,
        name="registar_pagamento"
    ),
    path(
        "pagamentos/<int:id_pagamento>/editar/",
        views.editar_pagamento,
        name="editar_pagamento"
    ),
    path(
        "pagamentos/<int:id_pagamento>/eliminar/",
        views.eliminar_pagamento,
        name="eliminar_pagamento"
    ),

    # ==========================================
    # FASE 2.2 — IMPORTAÇÃO E CONCILIAÇÃO BANCÁRIA
    # ==========================================

    # Importação CSV
    path(
        "movimentos-bancarios/importar/",
        views.importar_movimentos_csv,
        name="importar_movimentos_csv"
    ),

    # Conciliação
    path(
        "movimentos-bancarios/conciliacao/",
        views.listar_movimentos_nao_conciliados,
        name="listar_movimentos_nao_conciliados"
    ),
    path(
        "movimentos-bancarios/conciliacao/<int:id_movimento>/sugestoes/",
        views.ver_sugestoes_conciliacao,
        name="ver_sugestoes_conciliacao"
    ),
    path(
        "movimentos-bancarios/conciliacao/confirmar/",
        views.conciliar_movimento,
        name="conciliar_movimento"
    ),
    path(
        "movimentos-bancarios/conciliacao/desfazer/",
        views.desfazer_conciliacao_view,
        name="desfazer_conciliacao"
    ),
    path(
        "movimentos-bancarios/conciliacao/historico/",
        views.historico_conciliacoes,
        name="historico_conciliacoes"
    ),
    path(
        "movimentos-bancarios/conciliacao/suspeitos/",
        views.listar_movimentos_suspeitos,
        name="listar_movimentos_suspeitos"
    ),

    # Tipos de Documento
    path(
        "tipos-documento/",
        views.listar_tipos_documento,
        name="listar_tipos_documento"
    ),
    path(
        "tipos-documento/novo/",
        views.registar_tipo_documento,
        name="registar_tipo_documento"
    ),
    path(
        "tipos-documento/<int:id_tipo_documento>/editar/",
        views.editar_tipo_documento,
        name="editar_tipo_documento"
    ),
    path(
        "tipos-documento/<int:id_tipo_documento>/eliminar/",
        views.eliminar_tipo_documento,
        name="eliminar_tipo_documento"
    ),

    # Documentos
    path(
        "documentos/",
        views.listar_documentos,
        name="listar_documentos"
    ),
    path(
        "documentos/novo/",
        views.registar_documento,
        name="registar_documento"
    ),
    path(
        "documentos/<int:id_documento>/editar/",
        views.editar_documento,
        name="editar_documento"
    ),
    path(
        "documentos/<int:id_documento>/eliminar/",
        views.eliminar_documento,
        name="eliminar_documento"
    ),
    path(
        "documentos/<int:id_documento>/descarregar/",
        views.descarregar_documento,
        name="descarregar_documento"
    ),

    # ==========================================
    # ESTATÍSTICAS E AUDITORIA (Placeholder)
    # ==========================================

    path("estatisticas/", views.estatisticas, name="estatisticas"),
    path("auditoria/", views.auditoria, name="auditoria"),

]
