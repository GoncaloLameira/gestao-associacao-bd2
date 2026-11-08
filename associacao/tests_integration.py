"""
Integration Tests for Multi-Tenancy Isolation
Tests that procedures properly enforce association boundaries.
"""
import os
import psycopg2
from django.test import TestCase
from django.db import connection
from django.conf import settings
from associacao.database import obter_ligacao


def _get_raw_connection():
    """Get a raw psycopg2 connection for transaction control."""
    db = settings.DATABASES['default']
    return psycopg2.connect(
        dbname=db['NAME'],
        user=db['USER'],
        password=db['PASSWORD'],
        host=db['HOST'],
        port=db['PORT'],
    )


class MultiTenancyIsolationTests(TestCase):
    """
    Tests multi-tenancy isolation by creating two associations (A and B)
    and verifying that users from one association cannot access/modify
    data from the other association through database procedures.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Use raw psycopg2 connection for transaction control (savepoints)
        cls.conn = _get_raw_connection()
        cls.conn.autocommit = False

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        """Create two associations A and B with test data."""
        with self.conn.cursor() as cur:
            # COMPREHENSIVE CLEANUP: Truncate all tables used by this test
            # This ensures clean state regardless of test order or other tests' side effects
            cur.execute("""
                TRUNCATE TABLE
                    conciliacao_bancaria,
                    pagamento,
                    movimento_bancario,
                    documento,
                    tipo_documento,
                    exercicio_cargo,
                    cargo,
                    orgao_social,
                    mandato,
                    quota_associado,
                    quota,
                    associado,
                    evento,
                    associacao,
                    localidade
                RESTART IDENTITY CASCADE
            """)

            # Create localidade first
            cur.execute("""
                INSERT INTO localidade (nome_localidade, codigo_postal)
                VALUES ('Lisboa', '1000-001')
                ON CONFLICT (nome_localidade, codigo_postal) DO NOTHING
                RETURNING id_localidade
            """)
            loc_result = cur.fetchone()
            if loc_result:
                self.localidade_id = loc_result[0]
            else:
                cur.execute("SELECT id_localidade FROM localidade WHERE nome_localidade = 'Lisboa' AND codigo_postal = '1000-001'")
                self.localidade_id = cur.fetchone()[0]

            # Create Association A
            cur.execute("""
                INSERT INTO associacao (nipc, nome, data_fundacao, email, telefone, password_hash,
                    tipo_via, nome_via, numero_porta, andar, codigo_postal, id_localidade)
                VALUES ('123456789', 'Associacao A', '2020-01-01', 'a@test.pt', '111111111', 'hash_a',
                    'Rua', 'Rua A', '1', '1', '1000-001', %s)
                RETURNING id_associacao
            """, (self.localidade_id,))
            self.assoc_a_id = cur.fetchone()[0]

            # Create Association B
            cur.execute("""
                INSERT INTO associacao (nipc, nome, data_fundacao, email, telefone, password_hash,
                    tipo_via, nome_via, numero_porta, andar, codigo_postal, id_localidade)
                VALUES ('987654321', 'Associacao B', '2020-01-01', 'b@test.pt', '222222222', 'hash_b',
                    'Rua', 'Rua B', '2', '2', '2000-002', %s)
                RETURNING id_associacao
            """, (self.localidade_id,))
            self.assoc_b_id = cur.fetchone()[0]

            # Create orgão social for each association
            cur.execute("""
                INSERT INTO orgao_social (nome, descricao, id_associacao)
                VALUES ('Direção A', 'Direção da Associação A', %s)
                RETURNING id_orgao_social
            """, (self.assoc_a_id,))
            self.orgao_a_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO orgao_social (nome, descricao, id_associacao)
                VALUES ('Direção B', 'Direção da Associação B', %s)
                RETURNING id_orgao_social
            """, (self.assoc_b_id,))
            self.orgao_b_id = cur.fetchone()[0]

            # Create cargo for each association
            cur.execute("CALL registar_cargo('Presidente A', 'Presidente da Associação A', %s, %s)",
                       (self.orgao_a_id, self.assoc_a_id))
            cur.execute("SELECT id_cargo FROM cargo WHERE nome = 'Presidente A' AND id_orgao_social = %s",
                       (self.orgao_a_id,))
            self.cargo_a_id = cur.fetchone()[0]

            cur.execute("CALL registar_cargo('Presidente B', 'Presidente da Associação B', %s, %s)",
                       (self.orgao_b_id, self.assoc_b_id))
            cur.execute("SELECT id_cargo FROM cargo WHERE nome = 'Presidente B' AND id_orgao_social = %s",
                       (self.orgao_b_id,))
            self.cargo_b_id = cur.fetchone()[0]

            # Create mandato for each association
            cur.execute("CALL registar_mandato('2023-01-01', '2026-12-31', %s)", (self.assoc_a_id,))
            cur.execute("SELECT id_mandato FROM mandato WHERE id_associacao = %s ORDER BY id_mandato DESC LIMIT 1",
                       (self.assoc_a_id,))
            self.mandato_a_id = cur.fetchone()[0]

            cur.execute("CALL registar_mandato('2023-01-01', '2026-12-31', %s)", (self.assoc_b_id,))
            cur.execute("SELECT id_mandato FROM mandato WHERE id_associacao = %s ORDER BY id_mandato DESC LIMIT 1",
                       (self.assoc_b_id,))
            self.mandato_b_id = cur.fetchone()[0]

            # Create associado for each association
            cur.execute("""
                CALL registar_associado(1, 'Associado A', '111111111', '1990-01-01', 'a@test.pt', '111111111',
                    '2023-01-01', NULL, 'Ativo', 'Rua', 'Rua A', '1', '1', '1000-001', %s, %s)
            """, (self.localidade_id, self.assoc_a_id))
            cur.execute("SELECT id_associado FROM associado WHERE nif = '111111111' AND id_associacao = %s",
                       (self.assoc_a_id,))
            self.associado_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_associado(2, 'Associado B', '222222222', '1990-01-01', 'b@test.pt', '222222222',
                    '2023-01-01', NULL, 'Ativo', 'Rua', 'Rua B', '2', '2', '2000-002', %s, %s)
            """, (self.localidade_id, self.assoc_b_id))
            cur.execute("SELECT id_associado FROM associado WHERE nif = '222222222' AND id_associacao = %s",
                       (self.assoc_b_id,))
            self.associado_b_id = cur.fetchone()[0]

            # Create quota for each association
            cur.execute("""
                CALL registar_quota('Quota Anual A', 100.0, 'Anual', '2023-01-01', '2023-12-31', %s)
            """, (self.assoc_a_id,))
            cur.execute("SELECT id_quota FROM quota WHERE designacao_quota = 'Quota Anual A' AND id_associacao = %s",
                       (self.assoc_a_id,))
            self.quota_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_quota('Quota Anual B', 200.0, 'Anual', '2023-01-01', '2023-12-31', %s)
            """, (self.assoc_b_id,))
            cur.execute("SELECT id_quota FROM quota WHERE designacao_quota = 'Quota Anual B' AND id_associacao = %s",
                       (self.assoc_b_id,))
            self.quota_b_id = cur.fetchone()[0]

            # Create quota_associado for each association
            cur.execute("CALL gerar_quotas_associados(%s, '2023-01-01', 1)", (self.quota_a_id,))
            cur.execute("""
                SELECT id_quota_associado FROM quota_associado qa
                JOIN quota q ON qa.id_quota = q.id_quota
                WHERE q.id_quota = %s AND qa.id_associado = %s
            """, (self.quota_a_id, self.associado_a_id))
            self.qa_a_id = cur.fetchone()[0]

            cur.execute("CALL gerar_quotas_associados(%s, '2023-01-01', 1)", (self.quota_b_id,))
            cur.execute("""
                SELECT id_quota_associado FROM quota_associado qa
                JOIN quota q ON qa.id_quota = q.id_quota
                WHERE q.id_quota = %s AND qa.id_associado = %s
            """, (self.quota_b_id, self.associado_b_id))
            self.qa_b_id = cur.fetchone()[0]

            # Create evento for each association
            cur.execute("""
                CALL registar_evento('Evento A', 'Desc A', '2023-06-01 10:00', '2023-06-01 12:00',
                    'Local A', 'Agendado', %s)
            """, (self.assoc_a_id,))
            cur.execute("SELECT id_evento FROM evento WHERE nome_evento = 'Evento A' AND id_associacao = %s",
                       (self.assoc_a_id,))
            self.evento_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_evento('Evento B', 'Desc B', '2023-06-01 10:00', '2023-06-01 12:00',
                    'Local B', 'Agendado', %s)
            """, (self.assoc_b_id,))
            cur.execute("SELECT id_evento FROM evento WHERE nome_evento = 'Evento B' AND id_associacao = %s",
                       (self.assoc_b_id,))
            self.evento_b_id = cur.fetchone()[0]

            # Create tipo_documento for each association
            cur.execute("CALL registar_tipo_documento('Tipo A', 'Desc Tipo A', %s)", (self.assoc_a_id,))
            cur.execute("SELECT id_tipo_documento FROM tipo_documento WHERE nome_tipo_documento = 'Tipo A' AND id_associacao = %s",
                       (self.assoc_a_id,))
            self.tipo_doc_a_id = cur.fetchone()[0]

            cur.execute("CALL registar_tipo_documento('Tipo B', 'Desc Tipo B', %s)", (self.assoc_b_id,))
            cur.execute("SELECT id_tipo_documento FROM tipo_documento WHERE nome_tipo_documento = 'Tipo B' AND id_associacao = %s",
                       (self.assoc_b_id,))
            self.tipo_doc_b_id = cur.fetchone()[0]

            # Create documento for each association
            cur.execute("""
                CALL registar_documento(%s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s, %s, %s)
            """, ('Doc A', '2023-01-01 10:00:00', '2023-01-01', 'file_a.pdf', 'Obs A', self.tipo_doc_a_id, self.assoc_a_id, self.mandato_a_id))
            cur.execute("SELECT id_documento FROM documento WHERE nome_documento = 'Doc A' AND id_associacao = %s",
                       (self.assoc_a_id,))
            self.doc_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_documento(%s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s, %s, %s)
            """, ('Doc B', '2023-01-01 10:00:00', '2023-01-01', 'file_b.pdf', 'Obs B', self.tipo_doc_b_id, self.assoc_b_id, self.mandato_b_id))
            cur.execute("SELECT id_documento FROM documento WHERE nome_documento = 'Doc B' AND id_associacao = %s",
                       (self.assoc_b_id,))
            self.doc_b_id = cur.fetchone()[0]

            # Create movimento_bancario and pagamento for each association
            cur.execute("""
                CALL registar_movimento_bancario(%s::date, %s::varchar, %s::numeric(10,2), %s::varchar, %s::integer)
            """, ('2023-01-15', 'Mov A', 100.0, 'REF-A', self.assoc_a_id))
            cur.execute("SELECT id_movimento FROM movimento_bancario WHERE referencia_movimento = 'REF-A'")
            self.mov_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_pagamento(%s::timestamp, %s::numeric(10,2), %s::varchar, %s::varchar, %s, %s, %s, NULL)
            """, ('2023-01-15 10:00:00', 100.0, 'Transferencia', 'REF-A', self.qa_a_id, self.mov_a_id, self.assoc_a_id))
            cur.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", (self.qa_a_id,))
            self.pag_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_movimento_bancario(%s::date, %s::varchar, %s::numeric(10,2), %s::varchar, %s::integer)
            """, ('2023-01-15', 'Mov B', 200.0, 'REF-B', self.assoc_b_id))
            cur.execute("SELECT id_movimento FROM movimento_bancario WHERE referencia_movimento = 'REF-B'")
            self.mov_b_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_pagamento(%s::timestamp, %s::numeric(10,2), %s::varchar, %s::varchar, %s, %s, %s, NULL)
            """, ('2023-01-15 10:00:00', 200.0, 'Transferencia', 'REF-B', self.qa_b_id, self.mov_b_id, self.assoc_b_id))
            cur.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", (self.qa_b_id,))
            self.pag_b_id = cur.fetchone()[0]

            # Create exercicio_cargo for each association
            cur.execute("""
                CALL registar_exercicio_cargo('2023-01-01', '2026-12-31', %s, %s, %s, %s)
            """, (self.associado_a_id, self.cargo_a_id, self.mandato_a_id, self.assoc_a_id))
            cur.execute("SELECT id_exercicio_cargo FROM exercicio_cargo WHERE id_associado = %s AND id_cargo = %s",
                       (self.associado_a_id, self.cargo_a_id))
            self.exercicio_a_id = cur.fetchone()[0]

            cur.execute("""
                CALL registar_exercicio_cargo('2023-01-01', '2026-12-31', %s, %s, %s, %s)
            """, (self.associado_b_id, self.cargo_b_id, self.mandato_b_id, self.assoc_b_id))
            cur.execute("SELECT id_exercicio_cargo FROM exercicio_cargo WHERE id_associado = %s AND id_cargo = %s",
                       (self.associado_b_id, self.cargo_b_id))
            self.exercicio_b_id = cur.fetchone()[0]

            # Commit all setUp data since we're not in autocommit mode
            self.conn.commit()

    def tearDown(self):
        """Clean up test data."""
        # Rollback any aborted transaction on our connection
        # The setUp method does TRUNCATE before each test, so no need to delete here
        self.conn.rollback()

    # ============================================================
    # TEST 1: A cannot READ B's data via procedures
    # ============================================================

    def test_select_views_filter_by_associacao(self):
        """Views should filter by id_associacao."""
        with self.conn.cursor() as cur:
            # View vw_associados should only show A's associados when filtered
            cur.execute("SELECT * FROM vw_associados WHERE id_associacao = %s", (self.assoc_a_id,))
            associados_a = cur.fetchall()
            self.assertEqual(len(associados_a), 1)
            self.assertEqual(associados_a[0][2], 'Associado A')  # nome

            cur.execute("SELECT * FROM vw_associados WHERE id_associacao = %s", (self.assoc_b_id,))
            associados_b = cur.fetchall()
            self.assertEqual(len(associados_b), 1)
            self.assertEqual(associados_b[0][2], 'Associado B')

            # Cross-query should return empty
            cur.execute("SELECT * FROM vw_associados WHERE id_associacao = %s AND nome = 'Associado B'",
                       (self.assoc_a_id,))
            result = cur.fetchall()
            self.assertEqual(len(result), 0)

    # ============================================================
    # TEST 2: A cannot UPDATE B's data via procedures
    # ============================================================

    def _call_expecting_raise(self, cur, sql, params, expected_msg):
        """Helper to call a procedure expecting it to raise, using savepoint."""
        cur.execute("SAVEPOINT test_sp")
        try:
            cur.execute(sql, params)
            cur.execute("RELEASE SAVEPOINT test_sp")
            self.fail("Expected RaiseException")
        except psycopg2.errors.RaiseException as e:
            cur.execute("ROLLBACK TO SAVEPOINT test_sp")
            self.assertIn(expected_msg, str(e))

    def test_update_mandato_cross_associacao_fails(self):
        """Association A cannot update Association B's mandato."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_mandato(%s, '2024-01-01', '2027-12-31', %s)",
                (self.mandato_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

            # Verify B's mandato unchanged
            cur.execute("SELECT data_inicio FROM mandato WHERE id_mandato = %s", (self.mandato_b_id,))
            self.assertEqual(cur.fetchone()[0].year, 2023)

    def test_update_evento_cross_associacao_fails(self):
        """Association A cannot update Association B's evento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_evento(%s, %s::varchar, %s::varchar, %s::timestamp, %s::timestamp, %s::varchar, %s::varchar, %s::integer)",
                (self.evento_b_id, 'Evento Hacked', 'Desc', '2023-06-01 10:00', '2023-06-01 12:00', 'Local', 'Agendado', self.assoc_a_id),
                'não encontrado ou não autorizado')

            cur.execute("SELECT nome_evento FROM evento WHERE id_evento = %s", (self.evento_b_id,))
            self.assertEqual(cur.fetchone()[0], 'Evento B')

    def test_update_associado_cross_associacao_fails(self):
        """Association A cannot update Association B's associado."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL atualizar_associado(%s::integer, 999, 'Hacked', '999999999', '1990-01-01', 'hack@test.pt', '999999999',
                        '2023-01-01', NULL, 'Ativo', 'Rua', 'Rua', '99', '99', '9999-999', 1, %s::integer)
                """,
                (self.associado_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_update_quota_cross_associacao_fails(self):
        """Association A cannot update Association B's quota."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_quota(%s::integer, %s::varchar, %s::numeric, %s::varchar, %s::date, %s::date, %s::integer)",
                (self.quota_b_id, 'Hacked', 999.0, 'Mensal', '2023-01-01', '2023-12-31', self.assoc_a_id),
                'não encontrada ou não autorizada')

    def test_update_orgao_social_cross_associacao_fails(self):
        """Association A cannot update Association B's orgao_social."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_orgao_social(%s::integer, %s::varchar, %s::varchar, %s::integer)",
                (self.orgao_b_id, 'Hacked', 'Desc', self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_update_cargo_cross_associacao_fails(self):
        """Association A cannot update Association B's cargo."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_cargo(%s::integer, %s::varchar, %s::varchar, %s::integer, %s::integer)",
                (self.cargo_b_id, 'Hacked', 'Desc', self.orgao_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_update_quota_associado_cross_associacao_fails(self):
        """Association A cannot update Association B's quota_associado."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL atualizar_quota_associado(%s::integer, %s::numeric, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer)
                """,
                (self.qa_b_id, 999.0, '2023-01-01', '01/2023', 'Pendente', self.associado_b_id, self.quota_b_id, self.assoc_a_id),
                'não encontrada ou não autorizada')

    def test_update_pagamento_cross_associacao_fails(self):
        """Association A cannot update Association B's pagamento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL atualizar_pagamento(%s::integer, %s::timestamp, %s::numeric, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer)
                """,
                (self.pag_b_id, 'NOW()', 999.0, 'Hack', 'Hack', self.qa_b_id, self.mov_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_update_movimento_bancario_cross_associacao_fails(self):
        """Association A cannot update Association B's conciliado movimento_bancario."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_movimento_bancario(%s::integer, %s::date, %s::varchar, %s::numeric, %s::varchar, %s::integer)",
                (self.mov_b_id, '2023-01-15', 'Hacked', 999.0, 'HACK', self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_update_tipo_documento_cross_associacao_fails(self):
        """Association A cannot update Association B's tipo_documento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL atualizar_tipo_documento(%s::integer, %s::varchar, %s::varchar, %s::integer)",
                (self.tipo_doc_b_id, 'Hacked', 'Desc', self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_update_documento_cross_associacao_fails(self):
        """Association A cannot update Association B's documento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL atualizar_documento(%s::integer, %s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer)
                """,
                (self.doc_b_id, 'Hacked', 'NOW()', '2023-01-01', 'hack.pdf', 'Hack', self.tipo_doc_b_id, self.assoc_a_id, self.mandato_b_id),
                'não encontrado ou não autorizado')

    def test_update_exercicio_cargo_cross_associacao_fails(self):
        """Association A cannot update Association B's exercicio_cargo."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL atualizar_exercicio_cargo(%s::integer, %s::date, %s::date, %s::integer, %s::integer, %s::integer, %s::integer)
                """,
                (self.exercicio_b_id, '2023-01-01', '2026-12-31', self.associado_b_id, self.cargo_b_id, self.mandato_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    # ============================================================
    # TEST 3: A cannot DELETE B's data via procedures
    # ============================================================

    def test_delete_mandato_cross_associacao_fails(self):
        """Association A cannot delete Association B's mandato."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_mandato(%s, %s)", (self.mandato_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

            # Verify still exists
            cur.execute("SELECT 1 FROM mandato WHERE id_mandato = %s", (self.mandato_b_id,))
            self.assertIsNotNone(cur.fetchone())

    def test_delete_evento_cross_associacao_fails(self):
        """Association A cannot delete Association B's evento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_evento(%s, %s)", (self.evento_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_associado_cross_associacao_fails(self):
        """Association A cannot delete Association B's associado."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_associado(%s, %s)", (self.associado_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_quota_cross_associacao_fails(self):
        """Association A cannot delete Association B's quota."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_quota(%s, %s)", (self.quota_b_id, self.assoc_a_id),
                'não encontrada ou não autorizada')

    def test_delete_orgao_social_cross_associacao_fails(self):
        """Association A cannot delete Association B's orgao_social."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_orgao_social(%s, %s)", (self.orgao_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_cargo_cross_associacao_fails(self):
        """Association A cannot delete Association B's cargo."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_cargo(%s, %s)", (self.cargo_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_quota_associado_cross_associacao_fails(self):
        """Association A cannot delete Association B's quota_associado."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_quota_associado(%s, %s)", (self.qa_b_id, self.assoc_a_id),
                'não encontrada ou não autorizada')

    def test_delete_pagamento_cross_associacao_fails(self):
        """Association A cannot delete Association B's pagamento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_pagamento(%s, %s)", (self.pag_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_movimento_bancario_cross_associacao_fails(self):
        """Association A cannot delete Association B's conciliado movimento_bancario."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_movimento_bancario(%s, %s)", (self.mov_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_tipo_documento_cross_associacao_fails(self):
        """Association A cannot delete Association B's tipo_documento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_tipo_documento(%s, %s)", (self.tipo_doc_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_documento_cross_associacao_fails(self):
        """Association A cannot delete Association B's documento."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_documento(%s, %s)", (self.doc_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    def test_delete_exercicio_cargo_cross_associacao_fails(self):
        """Association A cannot delete Association B's exercicio_cargo."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL eliminar_exercicio_cargo(%s, %s)", (self.exercicio_b_id, self.assoc_a_id),
                'não encontrado ou não autorizado')

    # ============================================================
    # TEST 4: A cannot INSERT with B's foreign keys
    # ============================================================

    def test_registar_exercicio_cargo_with_foreign_keys_from_other_associacao_fails(self):
        """Cannot create exercicio_cargo using associado/cargo/mandato from another association."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL registar_exercicio_cargo(%s::date, %s::date, %s::integer, %s::integer, %s::integer, %s::integer)
                """, ('2023-01-01', '2026-12-31', self.associado_b_id, self.cargo_b_id, self.mandato_b_id, self.assoc_a_id),
                'não pertence à associação autorizada')

    def test_registar_cargo_with_orgao_from_other_associacao_fails(self):
        """Cannot create cargo using orgao_social from another association."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                "CALL registar_cargo(%s::varchar, %s::varchar, %s::integer, %s::integer)",
                ('Cargo Hack', 'Desc', self.orgao_b_id, self.assoc_a_id),
                'não pertence à associação autorizada')

    def test_registar_pagamento_with_qa_from_other_associacao_fails(self):
        """Cannot create pagamento using quota_associado from another association."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL registar_pagamento(%s::timestamp, %s::numeric, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer, NULL)
                """, ('NOW()', 100.0, 'Transferência', 'REF', self.qa_b_id, self.mov_a_id, self.assoc_a_id),
                'não pertence à associação autorizada')

    def test_registar_documento_with_tipo_from_other_associacao_fails(self):
        """Cannot create documento using tipo_documento from another association."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL registar_documento(%s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer)
                """, ('Doc Hack', 'NOW()', '2023-01-01', 'hack.pdf', 'Obs', self.tipo_doc_b_id, self.assoc_a_id, self.mandato_a_id),
                'não pertence à associação autorizada')

    def test_registar_documento_with_mandato_from_other_associacao_fails(self):
        """Cannot create documento using mandato from another association."""
        with self.conn.cursor() as cur:
            self._call_expecting_raise(cur,
                """
                    CALL registar_documento(%s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer)
                """, ('Doc Hack', 'NOW()', '2023-01-01', 'hack.pdf', 'Obs', self.tipo_doc_a_id, self.assoc_a_id, self.mandato_b_id),
                'não pertence à associação autorizada')

    # ============================================================
    # TEST 5: A CAN update/delete own data (positive tests)
    # ============================================================

    def test_update_own_mandato_succeeds(self):
        """Association A can update its own mandato."""
        with self.conn.cursor() as cur:
            cur.execute("CALL atualizar_mandato(%s, '2024-01-01', '2027-12-31', %s)",
                       (self.mandato_a_id, self.assoc_a_id))
            cur.execute("SELECT data_inicio, data_fim FROM mandato WHERE id_mandato = %s", (self.mandato_a_id,))
            result = cur.fetchone()
            self.assertEqual(result[0].year, 2024)
            self.assertEqual(result[1].year, 2027)

    def test_update_own_evento_succeeds(self):
        """Association A can update its own evento."""
        with self.conn.cursor() as cur:
            cur.execute("CALL atualizar_evento(%s, 'Evento A Atualizado', 'Desc', '2023-06-01 10:00', '2023-06-01 12:00', 'Local', 'Agendado', %s)",
                       (self.evento_a_id, self.assoc_a_id))
            cur.execute("SELECT nome_evento FROM evento WHERE id_evento = %s", (self.evento_a_id,))
            self.assertEqual(cur.fetchone()[0], 'Evento A Atualizado')

    def test_update_own_associado_succeeds(self):
        """Association A can update its own associado."""
        with self.conn.cursor() as cur:
            cur.execute("""
                CALL atualizar_associado(%s, 1, 'Associado A Atualizado', '111111111', '1990-01-01', 'a@test.pt', '111111111',
                    '2023-01-01', NULL, 'Ativo', 'Rua', 'Rua A', '1', '1', '1000-001', 1, %s)
            """, (self.associado_a_id, self.assoc_a_id))
            cur.execute("SELECT nome FROM associado WHERE id_associado = %s", (self.associado_a_id,))
            self.assertEqual(cur.fetchone()[0], 'Associado A Atualizado')

    def test_delete_own_mandato_succeeds(self):
        """Association A can delete its own mandato (after creating a new one)."""
        with self.conn.cursor() as cur:
            # Create a new mandato to delete
            cur.execute("CALL registar_mandato('2024-01-01', '2027-12-31', %s)", (self.assoc_a_id,))
            cur.execute("SELECT id_mandato FROM mandato WHERE id_associacao = %s ORDER BY id_mandato DESC LIMIT 1",
                       (self.assoc_a_id,))
            new_mandato_id = cur.fetchone()[0]

            cur.execute("CALL eliminar_mandato(%s, %s)", (new_mandato_id, self.assoc_a_id))
            cur.execute("SELECT 1 FROM mandato WHERE id_mandato = %s", (new_mandato_id,))
            self.assertIsNone(cur.fetchone())

    def test_own_crud_operations_work(self):
        """All CRUD operations work for own association data."""
        with self.conn.cursor() as cur:
            # Update quota
            cur.execute("CALL atualizar_quota(%s, 'Quota Atualizada', 150.0, 'Anual', '2023-01-01', '2023-12-31', %s)",
                       (self.quota_a_id, self.assoc_a_id))
            cur.execute("SELECT designacao_quota, valor_quota FROM quota WHERE id_quota = %s", (self.quota_a_id,))
            self.assertEqual(cur.fetchone(), ('Quota Atualizada', 150.0))

            # Update orgao_social
            cur.execute("CALL atualizar_orgao_social(%s, 'Direção A Atualizada', 'Desc', %s)",
                       (self.orgao_a_id, self.assoc_a_id))
            cur.execute("SELECT nome FROM orgao_social WHERE id_orgao_social = %s", (self.orgao_a_id,))
            self.assertEqual(cur.fetchone()[0], 'Direção A Atualizada')

            # Update cargo
            cur.execute("CALL atualizar_cargo(%s, 'Presidente A Atualizado', 'Desc', %s, %s)",
                       (self.cargo_a_id, self.orgao_a_id, self.assoc_a_id))
            cur.execute("SELECT nome FROM cargo WHERE id_cargo = %s", (self.cargo_a_id,))
            self.assertEqual(cur.fetchone()[0], 'Presidente A Atualizado')

            # Update tipo_documento
            cur.execute("CALL atualizar_tipo_documento(%s, 'Tipo A Atualizado', 'Desc', %s)",
                       (self.tipo_doc_a_id, self.assoc_a_id))
            cur.execute("SELECT nome_tipo_documento FROM tipo_documento WHERE id_tipo_documento = %s", (self.tipo_doc_a_id,))
            self.assertEqual(cur.fetchone()[0], 'Tipo A Atualizado')

            # Update documento
            cur.execute("""
                CALL atualizar_documento(%s::integer, %s::varchar, %s::timestamp, %s::date, %s::varchar, %s::varchar, %s::integer, %s::integer, %s::integer)
            """, (self.doc_a_id, 'Doc A Atualizado', 'NOW()', '2023-01-01', 'file_a.pdf', 'Obs', self.tipo_doc_a_id, self.assoc_a_id, self.mandato_a_id))
            cur.execute("SELECT nome_documento FROM documento WHERE id_documento = %s", (self.doc_a_id,))
            self.assertEqual(cur.fetchone()[0], 'Doc A Atualizado')

            # Update exercicio_cargo
            cur.execute("""
                CALL atualizar_exercicio_cargo(%s, '2023-01-01', '2025-12-31', %s, %s, %s, %s)
            """, (self.exercicio_a_id, self.associado_a_id, self.cargo_a_id, self.mandato_a_id, self.assoc_a_id))
            cur.execute("SELECT data_fim FROM exercicio_cargo WHERE id_exercicio_cargo = %s", (self.exercicio_a_id,))
            self.assertEqual(cur.fetchone()[0].year, 2025)

    # ============================================================
    # TEST 6: Non-conciliado movimento_bancario is now protected by association isolation
    # ============================================================

    def test_movimento_bancario_nao_conciliado_protegido_por_associacao(self):
        """Non-conciliado movimento_bancario is now protected by association isolation (all movements have id_associacao)."""
        with self.conn.cursor() as cur:
            # Create a non-conciliado movimento with association A
            cur.execute("""
                CALL registar_movimento_bancario(%s::date, %s::varchar, %s::numeric(10,2), %s::varchar, %s::integer)
            """, ('2023-02-01', 'Mov Non-Conciliado', 50.0, 'REF-NC', self.assoc_a_id))
            cur.execute("SELECT id_movimento FROM movimento_bancario WHERE referencia_movimento = 'REF-NC'")
            mov_nc_id = cur.fetchone()[0]

            # Should NOT be able to update with association B (different association!)
            self._call_expecting_raise(cur,
                "CALL atualizar_movimento_bancario(%s::integer, %s::date, %s::varchar, %s::numeric, %s::varchar, %s::integer)",
                (mov_nc_id, '2023-02-01', 'Updated', 60.0, 'REF-NC-UPD', self.assoc_b_id),
                'não encontrado ou não autorizado')

            # But CAN update with association A
            cur.execute("CALL atualizar_movimento_bancario(%s, '2023-02-01', 'Updated', 60.0, 'REF-NC-UPD', %s)",
                       (mov_nc_id, self.assoc_a_id))

            cur.execute("SELECT descricao_movimento, valor_movimento FROM movimento_bancario WHERE id_movimento = %s",
                       (mov_nc_id,))
            result = cur.fetchone()
            self.assertEqual(result[0], 'Updated')
            self.assertEqual(result[1], 60.0)

            # Cleanup
            cur.execute("CALL eliminar_movimento_bancario(%s, %s)", (mov_nc_id, self.assoc_a_id))

    # ============================================================
    # TEST 7: Conciliado movimento_bancario cannot be updated by other association
    # ============================================================

    def test_movimento_bancario_conciliado_nao_pode_ser_atualizado_por_outra_associacao(self):
        """Conciliado movimento_bancario cannot be updated by other association."""
        with self.conn.cursor() as cur:
            # mov_a_id is conciliado (has pagamento)
            with self.assertRaises(psycopg2.errors.RaiseException) as ctx:
                cur.execute("CALL atualizar_movimento_bancario(%s, '2023-01-15', 'Hacked', 999.0, 'HACK', %s)",
                           (self.mov_a_id, self.assoc_b_id))
            self.assertIn('não encontrado ou não autorizado', str(ctx.exception))

    # ============================================================
    # TEST 8: Views correctly filter by association
    # ============================================================

    def test_all_views_filter_by_associacao(self):
        """All views include id_associacao and filter correctly."""
        with self.conn.cursor() as cur:
            views_to_test = [
                ('vw_associados', 'id_associacao', 'id_associado', self.associado_a_id),
                ('vw_mandatos', 'id_associacao', 'id_mandato', self.mandato_a_id),
                ('vw_exercicios_cargo', 'id_associacao', 'id_exercicio_cargo', self.exercicio_a_id),
                ('vw_eventos', 'id_associacao', 'id_evento', self.evento_a_id),
                ('vw_quotas', 'id_associacao', 'id_quota', self.quota_a_id),
                ('vw_orgaos_sociais', 'id_associacao', 'id_orgao_social', self.orgao_a_id),
                ('vw_cargos', 'id_associacao', 'id_cargo', self.cargo_a_id),  # uses id_associacao from orgao_social
                ('vw_pagamentos', 'id_associacao', 'id_pagamento', self.pag_a_id),
                ('vw_movimentos_bancarios', 'id_associacao', 'id_movimento', self.mov_a_id),
                ('vw_tipos_documento', 'id_associacao', 'id_tipo_documento', self.tipo_doc_a_id),
                ('vw_documentos', 'id_associacao', 'id_documento', self.doc_a_id),
            ]

            for view_name, filter_col, id_col, expected_id in views_to_test:
                # Query with A's association - should return A's data
                cur.execute(f"SELECT * FROM {view_name} WHERE {filter_col} = %s", (self.assoc_a_id if filter_col == 'id_associacao' else self.orgao_a_id,))
                results = cur.fetchall()
                self.assertGreater(len(results), 0, f"View {view_name} should return data for association A")

                # Query with B's association - should return B's data (not A's)
                cur.execute(f"SELECT * FROM {view_name} WHERE {filter_col} = %s", (self.assoc_b_id if filter_col == 'id_associacao' else self.orgao_b_id,))
                results_b = cur.fetchall()
                # Verify A's specific ID is not in B's results
                cur.execute(f"SELECT * FROM {view_name} WHERE {filter_col} = %s AND {id_col} = %s",
                           (self.assoc_b_id if filter_col == 'id_associacao' else self.orgao_b_id, expected_id))
                results_a_in_b = cur.fetchall()
                self.assertEqual(len(results_a_in_b), 0, f"View {view_name} should not leak A's data to B")


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner

    # This allows running the test file directly
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['associacao.tests_integration'])
    exit(failures)