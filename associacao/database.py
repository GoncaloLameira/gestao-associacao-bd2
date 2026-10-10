import psycopg2

from django.conf import settings


def obter_ligacao():
    db = settings.DATABASES['default']

    return psycopg2.connect(
        dbname=db['NAME'],
        user=db['USER'],
        password=db['PASSWORD'],
        host=db['HOST'],
        port=db['PORT'],
    )


def inserir_mandato(data_inicio, data_fim, id_associacao):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL registar_mandato(%s, %s, %s);",
                (data_inicio, data_fim, id_associacao)
            )

        ligacao.commit()

    finally:
        ligacao.close()


def listar_mandatos():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM vw_mandatos;"
            )

            return cursor.fetchall()

    finally:
        ligacao.close()



def inserir_exercicio_cargo(
    data_inicio,
    data_fim,
    id_associado,
    id_cargo,
    id_mandato
):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL registar_exercicio_cargo(%s, %s, %s, %s, %s);",
                (
                    data_inicio,
                    data_fim,
                    id_associado,
                    id_cargo,
                    id_mandato
                )
            )

        ligacao.commit()

    finally:
        ligacao.close()


def listar_exercicios_cargo():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM vw_exercicios_cargo;"
            )

            return cursor.fetchall()

    finally:
        ligacao.close()

def listar_associados():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute("""
                SELECT id_associado, nome
                FROM associado
                ORDER BY nome;
            """)

            return cursor.fetchall()

    finally:
        ligacao.close()


def listar_cargos():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.id_cargo,
                    c.nome,
                    os.nome
                FROM cargo c
                JOIN orgao_social os
                    ON os.id_orgao_social = c.id_orgao_social
                ORDER BY os.nome, c.nome;
            """)

            return cursor.fetchall()

    finally:
        ligacao.close()


def listar_mandatos_para_selecao():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute("""
                SELECT
                    id_mandato,
                    data_inicio,
                    data_fim
                FROM mandato
                ORDER BY data_inicio DESC;
            """)

            return cursor.fetchall()

    finally:
        ligacao.close()


# ==========================================
# ASSOCIACAO
# ==========================================

def inserir_associacao(
    nipc,
    nome,
    data_fundacao,
    email,
    telefone,
    password_hash,
    tipo_via,
    nome_via,
    numero_porta,
    andar,
    codigo_postal,
    id_localidade
):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_associacao(
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                );
                """,
                (
                    nipc,
                    nome,
                    data_fundacao,
                    email,
                    telefone,
                    password_hash,
                    tipo_via,
                    nome_via,
                    numero_porta,
                    andar,
                    codigo_postal,
                    id_localidade
                )
            )

        ligacao.commit()

    finally:
        ligacao.close()


def listar_associacoes():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM vw_associacoes ORDER BY nome;"
            )

            return cursor.fetchall()

    finally:
        ligacao.close()


# ==========================================
# EVENTO
# ==========================================

def inserir_evento(
    nome_evento,
    descricao_evento,
    data_inicio_evento,
    data_fim_evento,
    local_evento,
    estado_evento,
    id_associacao
):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_evento(
                    %s,
                    %s,
                    %s::TIMESTAMP,
                    %s::TIMESTAMP,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    nome_evento,
                    descricao_evento,
                    data_inicio_evento,
                    data_fim_evento,
                    local_evento,
                    estado_evento,
                    id_associacao
                )
            )

        ligacao.commit()

    finally:
        ligacao.close()


def listar_eventos():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM vw_eventos
                ORDER BY data_inicio_evento DESC;
                """
            )

            return cursor.fetchall()

    finally:
        ligacao.close()


# ==========================================
# FUNCOES AUXILIARES
# ==========================================

def listar_localidades():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_localidade, nome_localidade
                FROM localidade
                ORDER BY nome_localidade;
                """
            )

            return cursor.fetchall()

    finally:
        ligacao.close()


def listar_associacoes_para_selecao():
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_associacao, nome
                FROM associacao
                ORDER BY nome;
                """
            )

            return cursor.fetchall()

    finally:
        ligacao.close()


# ==========================================
# ASSOCIADO
# ==========================================

def inserir_associado(
    numero_associado, nome, nif, data_nascimento,
    email, telefone, data_adesao, data_saida, estado,
    tipo_via, nome_via, numero_porta, andar, codigo_postal,
    id_localidade, id_associacao
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_associado(
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                );
                """,
                (
                    numero_associado, nome, nif, data_nascimento,
                    email, telefone, data_adesao, data_saida, estado,
                    tipo_via, nome_via, numero_porta, andar, codigo_postal,
                    id_localidade, id_associacao
                )
            )


def listar_associados_completos():
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM vw_associados
                ORDER BY numero_associado;
                """
            )
            return cursor.fetchall()


# ==========================================
# QUOTA
# ==========================================

def inserir_quota(
    designacao_quota, valor_quota, periodicidade_quota,
    data_inicio_quota, data_fim_quota, id_associacao
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_quota(
                    %s, %s, %s, %s, %s, %s
                );
                """,
                (
                    designacao_quota, valor_quota, periodicidade_quota,
                    data_inicio_quota, data_fim_quota, id_associacao
                )
            )


def listar_quotas():
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM vw_quotas
                ORDER BY data_inicio_quota DESC;
                """
            )
            return cursor.fetchall()


# ==========================================
# ÓRGÃO SOCIAL
# ==========================================

def inserir_orgao_social(nome, descricao, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_orgao_social(%s, %s, %s);
                """,
                (nome, descricao, id_associacao)
            )


def listar_orgaos_sociais():
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM vw_orgaos_sociais
                ORDER BY nome;
                """
            )
            return cursor.fetchall()


def listar_orgaos_sociais_para_selecao():
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_orgao_social, nome
                FROM orgao_social
                ORDER BY nome;
                """
            )
            return cursor.fetchall()


# ==========================================
# CARGO
# ==========================================

def inserir_cargo(nome, descricao, id_orgao_social):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_cargo(%s, %s, %s);
                """,
                (nome, descricao, id_orgao_social)
            )


def listar_cargos_completos():
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM vw_cargos
                ORDER BY nome;
                """
            )
            return cursor.fetchall()
