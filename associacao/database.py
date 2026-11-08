import csv
import io
import psycopg2
import json

from django.conf import settings
from django.db import connection as django_connection


class DjangoConnectionWrapper:
    """
    Wrapper para usar a conexão do Django como se fosse uma conexão psycopg2.
    Permite usar 'with obter_ligacao() as ligacao:' e 'ligacao.commit()'.
    """

    def __init__(self):
        self._conn = django_connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Django gere a transação automaticamente
        pass

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        # Commit a transação subjacente do psycopg2.
        # Necessário para TransactionTestCase que não usa transações automáticas.
        if hasattr(self._conn, 'connection') and self._conn.connection is not None:
            self._conn.connection.commit()

    def close(self):
        # Não fechamos a conexão do Django
        pass


def obter_ligacao():
    """
    Obtém uma conexão à base de dados.
    Usa a conexão do Django quando disponível (ex: durante testes),
    caso contrário cria uma nova conexão psycopg2.
    """
    # Sempre usar a conexão do Django se o Django estiver configurado
    # django_connection.connection pode ser None até o primeiro cursor,
    # mas o wrapper funciona mesmo assim
    try:
        from django.db import connection as django_connection
        # Verificar se estamos em contexto Django (settings configurado)
        if django_connection.settings_dict:
            return DjangoConnectionWrapper()
    except Exception:
        pass

    # Fallback: criar nova conexão psycopg2 (para scripts standalone)
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


def mandato_sobrepoe(data_inicio, data_fim, id_associacao, id_mandato=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM mandato
                    WHERE id_associacao = %s
                      AND id_mandato <> COALESCE(%s, -1)
                      AND data_inicio <= COALESCE(%s, 'infinity'::date)
                      AND COALESCE(data_fim, 'infinity'::date) >= %s
                )
            """, (id_associacao, id_mandato, data_fim, data_inicio))
            return cursor.fetchone()[0]


def listar_mandatos(id_associacao=None):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    "SELECT * FROM vw_mandatos WHERE id_associacao = %s;",
                    (id_associacao,)
                )
            else:
                cursor.execute("SELECT * FROM vw_mandatos;")

            return cursor.fetchall()

    finally:
        ligacao.close()


def inserir_exercicio_cargo(
    data_inicio,
    data_fim,
    id_associado,
    id_cargo,
    id_mandato,
    id_associacao
):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL registar_exercicio_cargo(%s, %s, %s, %s, %s, %s);",
                (
                    data_inicio,
                    data_fim,
                    id_associado,
                    id_cargo,
                    id_mandato,
                    id_associacao
                )
            )

        ligacao.commit()

    finally:
        ligacao.close()


def listar_exercicios_cargo(id_associacao=None):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    "SELECT * FROM vw_exercicios_cargo WHERE id_associacao = %s;",
                    (id_associacao,)
                )
            else:
                cursor.execute("SELECT * FROM vw_exercicios_cargo;")

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


def listar_associados_para_selecao(id_associacao=None):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT id_associado, nome
                    FROM associado
                    WHERE id_associacao = %s
                    ORDER BY nome;
                """, (id_associacao,))
            else:
                cursor.execute("""
                    SELECT id_associado, nome
                    FROM associado
                    ORDER BY nome;
                """)

            return cursor.fetchall()

    finally:
        ligacao.close()


def listar_cargos(id_associacao=None):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT
                        c.id_cargo,
                        c.nome,
                        os.nome
                    FROM cargo c
                    JOIN orgao_social os
                        ON os.id_orgao_social = c.id_orgao_social
                    WHERE c.id_associacao = %s
                    ORDER BY os.nome, c.nome;
                """, (id_associacao,))
            else:
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


def listar_mandatos_para_selecao(id_associacao=None):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT
                        id_mandato,
                        data_inicio,
                        data_fim
                    FROM mandato
                    WHERE id_associacao = %s
                    ORDER BY data_inicio DESC;
                """, (id_associacao,))
            else:
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


def associacao_existe_nipc(nipc):
    """Verifica se já existe uma associação com o NIPC dado."""
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM associacao WHERE nipc = %s;",
                (nipc,)
            )
            return cursor.fetchone() is not None

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


def listar_eventos(id_associacao=None):
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_eventos
                    WHERE id_associacao = %s
                    ORDER BY data_inicio_evento DESC;
                    """,
                    (id_associacao,)
                )
            else:
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


def listar_codigos_postais_com_localidades():
    """
    Retorna lista de códigos postais com as suas localidades para o dropdown.
    Formato: (codigo_postal, 'codigo_postal - localidade')
    """
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT codigo_postal, nome_localidade
                FROM localidade
                ORDER BY codigo_postal, nome_localidade;
                """
            )

            return cursor.fetchall()

    finally:
        ligacao.close()


def obter_localidade_por_codigo_postal(codigo_postal):
    """
    Retorna a primeira localidade associada a um código postal.
    """
    ligacao = obter_ligacao()

    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_localidade, nome_localidade
                FROM localidade
                WHERE codigo_postal = %s
                ORDER BY nome_localidade
                LIMIT 1;
                """,
                (codigo_postal,)
            )

            return cursor.fetchone()

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


def listar_associados_completos(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT a.id_associado, a.numero_associado, a.nome, a.nif, a.data_nascimento,
                           a.email, a.telefone, a.data_adesao, a.data_saida, a.estado,
                           a.tipo_via, a.nome_via, a.numero_porta, a.andar, a.codigo_postal,
                           a.id_localidade, l.nome_localidade, ass.nome AS nome_associacao
                    FROM associado a
                    LEFT JOIN localidade l ON a.id_localidade = l.id_localidade
                    JOIN associacao ass ON a.id_associacao = ass.id_associacao
                    WHERE a.id_associacao = %s
                    ORDER BY a.numero_associado;
                    """,
                    [id_associacao]
                )
            else:
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


def listar_quotas(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_quotas
                    WHERE id_associacao = %s
                    ORDER BY data_inicio_quota DESC;
                    """,
                    (id_associacao,)
                )
            else:
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


def listar_orgaos_sociais(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_orgaos_sociais
                    WHERE id_associacao = %s
                    ORDER BY nome;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_orgaos_sociais
                    ORDER BY nome;
                    """
                )
            return cursor.fetchall()


def listar_orgaos_sociais_para_selecao(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT id_orgao_social, nome
                    FROM orgao_social
                    WHERE id_associacao = %s
                    ORDER BY nome;
                    """,
                    (id_associacao,)
                )
            else:
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

def inserir_cargo(nome, descricao, id_orgao_social, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_cargo(%s, %s, %s, %s);
                """,
                (nome, descricao, id_orgao_social, id_associacao)
            )


def listar_cargos_completos(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_cargos
                    WHERE id_associacao = %s
                    ORDER BY nome;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_cargos
                    ORDER BY nome;
                    """
                )
            return cursor.fetchall()


# ==========================================
# UPDATE/DELETE FUNCTIONS
# ==========================================

# Mandato
def obter_mandato(id_mandato):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_mandatos WHERE id_mandato = %s;", (id_mandato,))
            return cursor.fetchone()


def atualizar_mandato(data_inicio, data_fim, id_associacao, id_mandato):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_mandato(%s, %s, %s, %s);",
                (id_mandato, data_inicio, data_fim, id_associacao)
            )


def eliminar_mandato(id_mandato, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_mandato(%s, %s);", (id_mandato, id_associacao))


def obter_composicao_mandato(id_mandato, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("""
                SELECT ec.id_exercicio_cargo, a.nome, c.nome, os.nome,
                       ec.data_inicio, ec.data_fim
                FROM exercicio_cargo ec
                JOIN associado a ON a.id_associado = ec.id_associado
                JOIN cargo c ON c.id_cargo = ec.id_cargo
                JOIN orgao_social os ON os.id_orgao_social = c.id_orgao_social
                JOIN mandato m ON m.id_mandato = ec.id_mandato
                WHERE ec.id_mandato = %s AND m.id_associacao = %s
                ORDER BY os.nome, c.nome, a.nome
            """, (id_mandato, id_associacao))
            return cursor.fetchall()


def passagem_posse(id_mandato_anterior, data_inicio, data_fim, id_presidente,
                   composicao, password_hash, id_associacao):
    """Executa a passagem de posse numa única transação PostgreSQL."""
    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL passagem_posse(%s, %s, %s, %s, %s::jsonb, %s, %s);",
                (id_mandato_anterior, data_inicio, data_fim, id_presidente,
                 json.dumps(composicao), password_hash, id_associacao),
            )
        ligacao.commit()
    finally:
        ligacao.close()


# ExercicioCargo
def obter_exercicio_cargo(id_exercicio_cargo):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_exercicios_cargo WHERE id_exercicio_cargo = %s;", (id_exercicio_cargo,))
            return cursor.fetchone()


def atualizar_exercicio_cargo(data_inicio, data_fim, id_associado, id_cargo, id_mandato, id_exercicio_cargo, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_exercicio_cargo(%s, %s, %s, %s, %s, %s, %s);",
                (id_exercicio_cargo, data_inicio, data_fim, id_associado, id_cargo, id_mandato, id_associacao)
            )


def eliminar_exercicio_cargo(id_exercicio_cargo, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_exercicio_cargo(%s, %s);", (id_exercicio_cargo, id_associacao))


# Associacao
def obter_associacao(id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_associacoes WHERE id_associacao = %s;", (id_associacao,))
            return cursor.fetchone()


def atualizar_associacao(
    id_associacao, nipc, nome, data_fundacao, email, telefone,
    password_hash, tipo_via, nome_via, numero_porta, andar,
    codigo_postal, id_localidade
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL atualizar_associacao(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
                """,
                (
                    id_associacao, nipc, nome, data_fundacao, email, telefone,
                    password_hash, tipo_via, nome_via, numero_porta, andar,
                    codigo_postal, id_localidade
                )
            )


def eliminar_associacao(id_associacao):
    # NOTA: A procedure eliminada não recebe id_associacao pois é a própria associação
    # Esta função mantém a assinatura original para compatibilidade
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_associacao(%s);", (id_associacao,))


# Evento
def obter_evento(id_evento):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_eventos WHERE id_evento = %s;", (id_evento,))
            return cursor.fetchone()


def atualizar_evento(
    id_evento, nome_evento, descricao_evento, data_inicio_evento,
    data_fim_evento, local_evento, estado_evento, id_associacao
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL atualizar_evento(
                    %s, %s, %s, %s::TIMESTAMP, %s::TIMESTAMP, %s, %s, %s
                );
                """,
                (
                    id_evento, nome_evento, descricao_evento, data_inicio_evento,
                    data_fim_evento, local_evento, estado_evento, id_associacao
                )
            )


def eliminar_evento(id_evento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_evento(%s, %s);", (id_evento, id_associacao))


# Associado
def obter_associado(id_associado):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_associados WHERE id_associado = %s;", (id_associado,))
            return cursor.fetchone()


def atualizar_associado(
    id_associado, numero_associado, nome, nif, data_nascimento,
    email, telefone, data_adesao, data_saida, estado,
    tipo_via, nome_via, numero_porta, andar, codigo_postal,
    id_localidade, id_associacao
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL atualizar_associado(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                );
                """,
                (
                    id_associado, numero_associado, nome, nif, data_nascimento,
                    email, telefone, data_adesao, data_saida, estado,
                    tipo_via, nome_via, numero_porta, andar, codigo_postal,
                    id_localidade, id_associacao
                )
            )


def eliminar_associado(id_associado, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_associado(%s, %s);", (id_associado, id_associacao))


# Quota
def obter_quota(id_quota):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_quotas WHERE id_quota = %s;", (id_quota,))
            return cursor.fetchone()


def atualizar_quota(
    id_quota, designacao_quota, valor_quota, periodicidade_quota,
    data_inicio_quota, data_fim_quota, id_associacao
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_quota(%s, %s, %s, %s, %s, %s, %s);",
                (id_quota, designacao_quota, valor_quota, periodicidade_quota,
                 data_inicio_quota, data_fim_quota, id_associacao)
            )


def eliminar_quota(id_quota, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_quota(%s, %s);", (id_quota, id_associacao))


# OrgaoSocial
def obter_orgao_social(id_orgao_social):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_orgaos_sociais WHERE id_orgao_social = %s;", (id_orgao_social,))
            return cursor.fetchone()


def atualizar_orgao_social(id_orgao_social, nome, descricao, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_orgao_social(%s, %s, %s, %s);",
                (id_orgao_social, nome, descricao, id_associacao)
            )


def eliminar_orgao_social(id_orgao_social, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_orgao_social(%s, %s);", (id_orgao_social, id_associacao))


# Cargo
def obter_cargo(id_cargo):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_cargos WHERE id_cargo = %s;", (id_cargo,))
            return cursor.fetchone()


def atualizar_cargo(id_cargo, nome, descricao, id_orgao_social, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_cargo(%s, %s, %s, %s, %s);",
                (id_cargo, nome, descricao, id_orgao_social, id_associacao)
            )


def eliminar_cargo(id_cargo, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_cargo(%s, %s);", (id_cargo, id_associacao))


# QuotaAssociado
def listar_quotas_associado(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT qa.*
                    FROM quota_associado qa
                    JOIN quota q ON qa.id_quota = q.id_quota
                    WHERE q.id_associacao = %s
                    ORDER BY qa.data_vencimento DESC;
                """, (id_associacao,))
            else:
                cursor.execute("SELECT * FROM quota_associado ORDER BY data_vencimento DESC;")
            return cursor.fetchall()


def obter_quota_associado(id_quota_associado):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM quota_associado WHERE id_quota_associado = %s;", (id_quota_associado,))
            return cursor.fetchone()


def atualizar_quota_associado(
    id_quota_associado, valor_devido, data_vencimento,
    periodo_referencia, estado_quota_associado,
    id_associado, id_quota, id_associacao
):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_quota_associado(%s, %s, %s, %s, %s, %s, %s, %s);",
                (id_quota_associado, valor_devido, data_vencimento,
                 periodo_referencia, estado_quota_associado,
                 id_associado, id_quota, id_associacao)
            )


def eliminar_quota_associado(id_quota_associado, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_quota_associado(%s, %s);", (id_quota_associado, id_associacao))


def gerar_quotas_associados(id_quota, data_vencimento_inicial, periodos=12):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL gerar_quotas_associados(%s, %s, %s);",
                (id_quota, data_vencimento_inicial, periodos)
            )


# ==========================================
# MOVIMENTO BANCÁRIO
# ==========================================

def inserir_movimento_bancario(data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_movimento_bancario(%s, %s, %s, %s, %s);
                """,
                (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao)
            )


def listar_movimentos_bancarios(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_movimentos_bancarios
                    WHERE id_associacao = %s
                    ORDER BY data_movimento DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_movimentos_bancarios
                    ORDER BY data_movimento DESC;
                    """
                )
            return cursor.fetchall()


def obter_movimento_bancario(id_movimento):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_movimentos_bancarios WHERE id_movimento = %s;", (id_movimento,))
            return cursor.fetchone()


def atualizar_movimento_bancario(id_movimento, data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_movimento_bancario(%s, %s, %s, %s, %s, %s);",
                (id_movimento, data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao)
            )


def eliminar_movimento_bancario(id_movimento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_movimento_bancario(%s, %s);", (id_movimento, id_associacao))


# ==========================================
# PAGAMENTO
# ==========================================

def inserir_pagamento(data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, id_movimento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);
                """,
                (data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, id_movimento, id_associacao)
            )
            result = cursor.fetchone()
            return result[0] if result else None


def listar_pagamentos(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_pagamentos
                    WHERE id_associacao = %s
                    ORDER BY data_pagamento DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_pagamentos
                    ORDER BY data_pagamento DESC;
                    """
                )
            return cursor.fetchall()


def obter_pagamento(id_pagamento):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_pagamentos WHERE id_pagamento = %s;", (id_pagamento,))
            return cursor.fetchone()


def atualizar_pagamento(id_pagamento, data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, id_movimento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_pagamento(%s, %s, %s, %s, %s, %s, %s, %s);",
                (id_pagamento, data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, id_movimento, id_associacao)
            )


def eliminar_pagamento(id_pagamento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_pagamento(%s, %s);", (id_pagamento, id_associacao))


# ==========================================
# FUNÇÕES AUXILIARES PARA PAGAMENTOS
# ==========================================

def listar_quotas_associado_para_pagamento(id_associacao=None):
    """Retorna quotas associado pendentes ou em dívida para seleção no formulário de pagamento"""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT
                        qa.id_quota_associado,
                        a.nome,
                        a.numero_associado,
                        q.designacao_quota,
                        qa.periodo_referencia,
                        qa.valor_devido,
                        qa.estado_quota_associado
                    FROM quota_associado qa
                    JOIN associado a ON qa.id_associado = a.id_associado
                    JOIN quota q ON qa.id_quota = q.id_quota
                    WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida', 'Parcial')
                    AND q.id_associacao = %s
                    ORDER BY qa.data_vencimento;
                """, (id_associacao,))
            else:
                cursor.execute("""
                    SELECT
                        qa.id_quota_associado,
                        a.nome,
                        a.numero_associado,
                        q.designacao_quota,
                        qa.periodo_referencia,
                        qa.valor_devido,
                        qa.estado_quota_associado
                    FROM quota_associado qa
                    JOIN associado a ON qa.id_associado = a.id_associado
                    JOIN quota q ON qa.id_quota = q.id_quota
                    WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida', 'Parcial')
                    ORDER BY qa.data_vencimento;
                """)
            return cursor.fetchall()


def listar_movimentos_bancarios_para_selecao(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT mb.id_movimento, mb.data_movimento, mb.descricao_movimento, mb.valor_movimento
                    FROM movimento_bancario mb
                    LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
                    LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
                    LEFT JOIN quota q ON qa.id_quota = q.id_quota
                    WHERE q.id_associacao = %s
                    ORDER BY mb.data_movimento DESC;
                """, (id_associacao,))
            else:
                cursor.execute("""
                    SELECT id_movimento, data_movimento, descricao_movimento, valor_movimento
                    FROM movimento_bancario
                    ORDER BY data_movimento DESC;
                """)
            return cursor.fetchall()


# ==========================================
# TIPO DOCUMENTO
# ==========================================

def inserir_tipo_documento(nome_tipo_documento, descricao_tipo_documento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_tipo_documento(%s, %s, %s);
                """,
                (nome_tipo_documento, descricao_tipo_documento, id_associacao)
            )


def listar_tipos_documento(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_tipos_documento
                    WHERE id_associacao = %s
                    ORDER BY nome_tipo_documento;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_tipos_documento
                    ORDER BY nome_tipo_documento;
                    """
                )
            return cursor.fetchall()


def obter_tipo_documento(id_tipo_documento):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_tipos_documento WHERE id_tipo_documento = %s;", (id_tipo_documento,))
            return cursor.fetchone()


def atualizar_tipo_documento(id_tipo_documento, nome_tipo_documento, descricao_tipo_documento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL atualizar_tipo_documento(%s, %s, %s, %s);",
                (id_tipo_documento, nome_tipo_documento, descricao_tipo_documento, id_associacao)
            )


def eliminar_tipo_documento(id_tipo_documento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_tipo_documento(%s, %s);", (id_tipo_documento, id_associacao))


# ==========================================
# DOCUMENTO
# ==========================================

def inserir_documento(nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL registar_documento(%s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer);
                """,
                (nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato)
            )


def listar_documentos(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_documentos
                    WHERE id_associacao = %s
                    ORDER BY data_upload DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_documentos
                    ORDER BY data_upload DESC;
                    """
                )
            return cursor.fetchall()


def obter_documento(id_documento):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("SELECT * FROM vw_documentos WHERE id_documento = %s;", (id_documento,))
            return cursor.fetchone()


def atualizar_documento(id_documento, nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                """
                CALL atualizar_documento(%s::integer, %s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer);
                """,
                (id_documento, nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato)
            )


def eliminar_documento(id_documento, id_associacao):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute("CALL eliminar_documento(%s, %s);", (id_documento, id_associacao))


# ==========================================
# FUNÇÕES AUXILIARES PARA DOCUMENTOS
# ==========================================

def listar_tipos_documento_para_selecao(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT id_tipo_documento, nome_tipo_documento
                    FROM tipo_documento
                    WHERE id_associacao = %s
                    ORDER BY nome_tipo_documento;
                """, (id_associacao,))
            else:
                cursor.execute("""
                    SELECT id_tipo_documento, nome_tipo_documento
                    FROM tipo_documento
                    ORDER BY nome_tipo_documento;
                """)
            return cursor.fetchall()


def listar_mandatos_para_selecao(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT id_mandato, data_inicio, data_fim
                    FROM mandato
                    WHERE id_associacao = %s
                    ORDER BY data_inicio DESC;
                """, (id_associacao,))
            else:
                cursor.execute("""
                    SELECT id_mandato, data_inicio, data_fim
                    FROM mandato
                    ORDER BY data_inicio DESC;
""")
            return cursor.fetchall()


# ==========================================
# FUNÇÕES AUXILIARES PARA FICHEIROS
# ==========================================

def guardar_ficheiro_documento(ficheiro, id_associacao):
    """
    Guarda o ficheiro carregado no sistema de ficheiros.
    Retorna o caminho relativo ao MEDIA_ROOT.
    """
    import os
    import uuid
    from django.conf import settings
    from datetime import datetime

    # Criar diretório se não existir
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'documentos', str(id_associacao))
    os.makedirs(upload_dir, exist_ok=True)

    # Gerar nome único para evitar conflitos
    ext = os.path.splitext(ficheiro.name)[1].lower()
    nome_unico = f"{uuid.uuid4().hex}{ext}"

    # Caminho completo
    caminho_completo = os.path.join(upload_dir, nome_unico)

    # Guardar ficheiro
    with open(caminho_completo, 'wb+') as destino:
        for chunk in ficheiro.chunks():
            destino.write(chunk)

    # Retornar caminho relativo ao MEDIA_ROOT
    caminho_relativo = os.path.join('documentos', str(id_associacao), nome_unico)
    return caminho_relativo


def obter_caminho_ficheiro_documento(caminho_relativo):
    """
    Obtém o caminho absoluto do ficheiro a partir do caminho relativo.
    """
    from django.conf import settings
    import os
    return os.path.join(settings.MEDIA_ROOT, caminho_relativo)


def eliminar_ficheiro_documento(caminho_relativo):
    """
    Elimina o ficheiro físico do sistema de ficheiros.
    """
    import os
    from django.conf import settings

    if not caminho_relativo:
        return

    caminho_completo = os.path.join(settings.MEDIA_ROOT, caminho_relativo)
    if os.path.exists(caminho_completo):
        try:
            os.remove(caminho_completo)
        except OSError:
            pass  # Ignorar erros de eliminação


# ==========================================
# FASE 2.2 — IMPORTAÇÃO E CONCILIAÇÃO BANCÁRIA
# ==========================================

def importar_movimentos_csv(conteudo_csv, id_associacao, delimitador=',', tem_cabecalho=True, encoding='utf-8'):
    """
    Importa movimentos bancários de conteúdo CSV usando Python's csv module.
    Suporta: campos com aspas, delimitadores dentro de campos, quebras de linha em campos,
    cabeçalho opcional, encoding UTF-8, limites de tamanho.
    Formato CSV: data_movimento,valor_movimento,descricao_movimento,referencia_movimento[,id_externo_banco]

    Retorna tupla: (importados, duplicados, suspeitos, erros, erros_detalhe)
    """
    import hashlib

    # Validar tamanho do conteúdo (máximo 10MB)
    if len(conteudo_csv.encode(encoding)) > 10 * 1024 * 1024:
        return (0, 0, 0, 1, ['Ficheiro excede o limite de 10MB'])

    # Parsear CSV com Python's csv module
    try:
        # Detectar delimitador automaticamente se não especificado
        if delimitador == 'auto':
            sniffer = csv.Sniffer()
            sample = conteudo_csv[:1024]
            delimitador = sniffer.sniff(sample).delimiter

        # Criar reader com suporte a aspas e campos com quebras de linha
        csv_file = io.StringIO(conteudo_csv)
        reader = csv.reader(csv_file, delimiter=delimitador, quotechar='"', quoting=csv.QUOTE_MINIMAL)

        linhas = list(reader)
    except Exception as e:
        return (0, 0, 0, 1, [f'Erro ao parsear CSV: {str(e)}'])

    # Pular cabeçalho se necessário
    if tem_cabecalho and linhas:
        linhas = linhas[1:]

    # Validar e preparar dados
    movimentos_validos = []
    erros_detalhe = []
    erros = 0

    for idx, linha in enumerate(linhas, start=1):
        if tem_cabecalho:
            linha_num = idx + 1
        else:
            linha_num = idx

        # Ignorar linhas completamente vazias
        if not any(campo.strip() for campo in linha):
            continue

        # Validar número de campos (mínimo 4: data, valor, descrição, referência; opcional 5: id_externo_banco)
        if len(linha) < 4:
            erros += 1
            erros_detalhe.append(f'Linha {linha_num}: Esperados pelo menos 4 campos, encontrados {len(linha)}')
            continue

        # Extrair campos
        data_str = linha[0].strip() if len(linha) > 0 else ''
        valor_str = linha[1].strip() if len(linha) > 1 else ''
        descricao = linha[2].strip() if len(linha) > 2 else ''
        referencia = linha[3].strip() if len(linha) > 3 else ''
        id_externo_banco = linha[4].strip() if len(linha) > 4 else ''

        # Validar data (ISO YYYY-MM-DD)
        try:
            from datetime import datetime
            data_movimento = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            erros += 1
            erros_detalhe.append(f'Linha {linha_num}: Data inválida "{data_str}" (formato esperado: YYYY-MM-DD)')
            continue

        # Validar valor (suporta vírgula decimal pt-PT)
        try:
            valor_normalizado = valor_str.replace(',', '.')
            valor_movimento = float(valor_normalizado)
            # Validar range razoável
            if abs(valor_movimento) > 99999999.99:
                raise ValueError("Valor fora do intervalo permitido")
        except ValueError:
            erros += 1
            erros_detalhe.append(f'Linha {linha_num}: Valor inválido "{valor_str}"')
            continue

        # Validar descrição (obrigatória)
        if not descricao:
            erros += 1
            erros_detalhe.append(f'Linha {linha_num}: Descrição vazia')
            continue

        # Referência opcional - None se vazia
        if not referencia:
            referencia = None

        # id_externo_banco opcional - None se vazia
        if not id_externo_banco:
            id_externo_banco = None

        # Calcular hash da linha original (reconstruída para consistência)
        # Usamos os campos normalizados para o hash
        linha_normalizada = f'{data_str}{delimitador}{valor_str}{delimitador}{descricao}{delimitador}{referencia or ""}'
        if id_externo_banco:
            linha_normalizada += f'{delimitador}{id_externo_banco}'
        hash_linha = hashlib.sha256(linha_normalizada.encode(encoding)).hexdigest()

        movimentos_validos.append({
            'data_movimento': data_movimento,
            'valor_movimento': valor_movimento,
            'descricao_movimento': descricao,
            'referencia_movimento': referencia,
            'id_externo_banco': id_externo_banco,
            'hash_linha': hash_linha,
        })

    # Se não há movimentos válidos, retornar erro
    if not movimentos_validos and erros == 0:
        return (0, 0, 0, 1, ['Nenhum movimento válido encontrado no CSV'])

    # Inserir movimentos na base de dados (transação única)
    importados = 0
    duplicados = 0
    suspeitos = 0

    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            for mov in movimentos_validos:
                # 1. Verificar se já existe movimento com mesmo hash (reimportação do mesmo ficheiro)
                cursor.execute(
                    """
                    SELECT id_movimento FROM movimento_bancario
                    WHERE id_associacao = %s AND hash_importacao = %s
                    """,
                    (id_associacao, mov['hash_linha'])
                )
                hash_existente = cursor.fetchone()

                if hash_existente:
                    duplicados += 1
                    continue

                # 2. Se tem id_externo_banco, tentar inserir com ON CONFLICT (idempotência por ID bancário)
                if mov['id_externo_banco'] is not None:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao, id_externo_banco, hash_importacao)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (mov['data_movimento'], mov['descricao_movimento'], mov['valor_movimento'],
                             mov['referencia_movimento'], id_associacao, mov['id_externo_banco'], mov['hash_linha'])
                        )
                        importados += 1
                    except Exception as e:
                        # Verificar se é violação de unique constraint em (id_associacao, id_externo_banco)
                        if 'uk_movimento_bancario_id_externo_banco' in str(e) or 'unique constraint' in str(e).lower():
                            duplicados += 1
                        else:
                            raise
                else:
                    # 3. Sem id_externo_banco: verificar duplicado por (data, valor, referência, associação)
                    cursor.execute(
                        """
                        SELECT id_movimento FROM movimento_bancario
                        WHERE id_associacao = %s
                          AND data_movimento = %s
                          AND valor_movimento = %s
                          AND (referencia_movimento IS NOT DISTINCT FROM %s)
                        """,
                        (id_associacao, mov['data_movimento'], mov['valor_movimento'], mov['referencia_movimento'])
                    )
                    existente = cursor.fetchone()

                    if existente:
                        # Existe movimento com mesma data/valor/referência mas sem ID bancário
                        # Inserir como suspeito_duplicado = true
                        cursor.execute(
                            """
                            INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao, hash_importacao, suspeito_duplicado)
                            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                            """,
                            (mov['data_movimento'], mov['descricao_movimento'], mov['valor_movimento'],
                             mov['referencia_movimento'], id_associacao, mov['hash_linha'])
                        )
                        suspeitos += 1
                    else:
                        # 4. Novo movimento único
                        cursor.execute(
                            """
                            INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao, hash_importacao)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (mov['data_movimento'], mov['descricao_movimento'], mov['valor_movimento'],
                             mov['referencia_movimento'], id_associacao, mov['hash_linha'])
                        )
                        importados += 1

            ligacao.commit()

    return (importados, duplicados, suspeitos, erros, erros_detalhe)


def listar_movimentos_suspeitos(id_associacao=None):
    """Lista movimentos bancários marcados como suspeitos de duplicação para revisão manual."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_movimentos_suspeitos
                    WHERE id_associacao = %s
                    ORDER BY data_movimento DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_movimentos_suspeitos
                    ORDER BY data_movimento DESC;
                    """
                )
            return cursor.fetchall()


def listar_movimentos_nao_conciliados(id_associacao=None):
    """Lista movimentos bancários sem pagamento associado."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            print(f"DEBUG LIST: connection type={type(ligacao)}, cursor connection={cursor.connection}")
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_movimentos_nao_conciliados
                    WHERE id_associacao = %s
                    ORDER BY data_movimento DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_movimentos_nao_conciliados
                    ORDER BY data_movimento DESC;
                    """
                )
            result = cursor.fetchall()
            print(f"DEBUG LIST: found {len(result)} movements")
            return result


def listar_pagamentos_sem_movimento(id_associacao=None):
    """Lista pagamentos sem movimento bancário associado."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_pagamentos_sem_movimento
                    WHERE id_associacao = %s
                    ORDER BY data_pagamento DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_pagamentos_sem_movimento
                    ORDER BY data_pagamento DESC;
                    """
                )
            return cursor.fetchall()


def encontrar_correspondencias_conciliacao(id_movimento, id_associacao):
    """Encontra pagamentos que correspondem a um movimento para conciliação."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM encontrar_correspondencias_conciliacao(%s, %s);",
                (id_movimento, id_associacao)
            )
            return cursor.fetchall()


def conciliar_movimento_pagamento(id_associacao, id_movimento, id_pagamento, forcar=False):
    """Confirma a conciliação entre um movimento e um pagamento."""
    try:
        with obter_ligacao() as ligacao:
            with ligacao.cursor() as cursor:
                cursor.execute(
                    "CALL conciliar_movimento_pagamento(%s, %s, %s, %s);",
                    (id_associacao, id_movimento, id_pagamento, forcar)
                )
        return True
    except Exception as e:
        # Erros de regra de negócio esperados - retorna False
        error_msg = str(e)
        if 'Correspondência ambígua' in error_msg:
            return False
        if 'já está conciliado' in error_msg or 'já tem movimento' in error_msg:
            return False
        # Outros erros (autorização, etc.) propagam
        raise


def desfazer_conciliacao(id_associacao, id_conciliacao, motivo='Reversão manual', utilizador=None):
    """Remove a conciliação ativa entre um movimento e um pagamento, preservando histórico."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "CALL desfazer_conciliacao(%s, %s, %s, %s);",
                (id_associacao, id_conciliacao, motivo, utilizador)
            )
    return True


def listar_conciliacoes(id_associacao=None):
    """Lista histórico de conciliações realizadas."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_conciliacoes
                    WHERE id_associacao = %s
                    ORDER BY data_pagamento DESC;
                    """,
                    (id_associacao,)
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM vw_conciliacoes
                    ORDER BY data_pagamento DESC;
                    """
                )
            return cursor.fetchall()


def listar_sugestoes_conciliacao(id_associacao, id_movimento=None):
    """Lista sugestões de conciliação. Se id_movimento for fornecido, retorna sugestões para esse movimento específico."""
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_movimento is not None:
                # Usar a function que encontra correspondências para um movimento específico
                cursor.execute(
                    "SELECT * FROM encontrar_correspondencias_conciliacao(%s, %s);",
                    (id_movimento, id_associacao)
                )
            else:
                # Retornar todas as sugestões da view
                if id_associacao:
                    cursor.execute(
                        """
                        SELECT *
                        FROM vw_sugestoes_conciliacao
                        WHERE id_associacao = %s
                        ORDER BY data_movimento DESC;
                        """,
                        (id_associacao,)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT *
                        FROM vw_sugestoes_conciliacao
                        ORDER BY data_movimento DESC;
                        """
                    )
            return cursor.fetchall()


def listar_mandatos_para_selecao(id_associacao=None):
    with obter_ligacao() as ligacao:
        with ligacao.cursor() as cursor:
            if id_associacao:
                cursor.execute("""
                    SELECT id_mandato, data_inicio, data_fim
                    FROM mandato
                    WHERE id_associacao = %s
                    ORDER BY data_inicio DESC;
                """, (id_associacao,))
            else:
                cursor.execute("""
                    SELECT id_mandato, data_inicio, data_fim
                    FROM mandato
                    ORDER BY data_inicio DESC;
""")
            return cursor.fetchall()


# ==========================================
# FUNÇÕES AUXILIARES PARA FICHEIROS
# ==========================================

def guardar_ficheiro_documento(ficheiro, id_associacao):
    """
    Guarda o ficheiro carregado no sistema de ficheiros.
    Retorna o caminho relativo ao MEDIA_ROOT.
    """
    import os
    import uuid
    from django.conf import settings
    from datetime import datetime

    # Criar diretório se não existir
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'documentos', str(id_associacao))
    os.makedirs(upload_dir, exist_ok=True)

    # Gerar nome único para evitar conflitos
    ext = os.path.splitext(ficheiro.name)[1].lower()
    nome_unico = f"{uuid.uuid4().hex}{ext}"

    # Caminho completo
    caminho_completo = os.path.join(upload_dir, nome_unico)

    # Guardar ficheiro
    with open(caminho_completo, 'wb+') as destino:
        for chunk in ficheiro.chunks():
            destino.write(chunk)

    # Retornar caminho relativo ao MEDIA_ROOT
    caminho_relativo = os.path.join('documentos', str(id_associacao), nome_unico)
    return caminho_relativo


def obter_caminho_ficheiro_documento(caminho_relativo):
    """
    Obtém o caminho absoluto do ficheiro a partir do caminho relativo.
    """
    from django.conf import settings
    import os
    return os.path.join(settings.MEDIA_ROOT, caminho_relativo)


def eliminar_ficheiro_documento(caminho_relativo):
    """
    Elimina o ficheiro físico do sistema de ficheiros.
    """
    import os
    from django.conf import settings

    if not caminho_relativo:
        return

    caminho_completo = os.path.join(settings.MEDIA_ROOT, caminho_relativo)
    if os.path.exists(caminho_completo):
        try:
            os.remove(caminho_completo)
        except OSError:
            pass  # Ignorar erros de eliminação
