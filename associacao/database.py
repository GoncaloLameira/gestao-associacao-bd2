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