#!/usr/bin/env python3
"""
Teste da Migração 11 - Recálculo de estados de quota_associado
"""

import os
import sys
import uuid

sys.path.insert(0, '/Users/goncalo/Documents/BD2/gestao_associacao')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projeto.settings')

import django
django.setup()

from django.db import connection
from django.test import TransactionTestCase
from decimal import Decimal
from datetime import date, timedelta


def create_test_associacao(cursor, nipc, nome='Associação Teste'):
    cursor.execute("""
        INSERT INTO associacao (nipc, nome, password_hash, email)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (nipc) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id_associacao
    """, [nipc, nome, 'pbkdf2_sha256$1000000$gX3hSIFgzSq3pDY1q9uTIA$UYkfnS0B/vlyi3rZuTZ3Wxxa+PQKAvbeFjjGgwPy9zU=', 'direcao@teste.pt'])
    return cursor.fetchone()[0]


def create_test_associado(cursor, id_associacao, numero, nif, estado='Ativo'):
    cursor.execute("""
        INSERT INTO associado (numero_associado, nome, nif, data_adesao, estado, id_associacao)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_associado
    """, [numero, f'Associado {numero}', nif, date.today() - timedelta(days=365), estado, id_associacao])
    return cursor.fetchone()[0]


def create_test_quota(cursor, id_associacao, valor=30.00, periodicidade='Mensal'):
    cursor.execute("""
        INSERT INTO quota (designacao_quota, valor_quota, periodicidade_quota, data_inicio_quota, id_associacao)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id_quota
    """, [f'Quota {periodicidade}', valor, periodicidade, date.today() - timedelta(days=30), id_associacao])
    return cursor.fetchone()[0]


def create_test_quota_associado(cursor, id_associado, id_quota, valor_devido=30.00, estado='Pendente', periodo='01/2025'):
    cursor.execute("""
        INSERT INTO quota_associado (valor_devido, data_vencimento, periodo_referencia, estado_quota_associado, id_associado, id_quota)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_quota_associado
    """, [valor_devido, date.today() + timedelta(days=30), periodo, estado, id_associado, id_quota])
    return cursor.fetchone()[0]


def get_quota_associado_estado(cursor, id_quota_associado):
    cursor.execute("SELECT estado_quota_associado FROM quota_associado WHERE id_quota_associado = %s", [id_quota_associado])
    row = cursor.fetchone()
    return row[0] if row else None


def get_pagamentos_total(cursor, id_quota_associado):
    cursor.execute("SELECT COALESCE(SUM(valor_pago), 0) FROM pagamento WHERE id_quota_associado = %s", [id_quota_associado])
    return cursor.fetchone()[0]


class Migration11Tests(TransactionTestCase):
    """Testes para Migração 11 - Recálculo de estados."""

    reset_sequences = True

    def setUp(self):
        test_id = str(uuid.uuid4().int)[:8]

        with connection.cursor() as cursor:
            nipc_a = f'1{test_id}'[:9]
            self.id_associacao_a = create_test_associacao(cursor, nipc_a, f'Associação A {test_id}')
            self.id_associado_a1 = create_test_associado(cursor, self.id_associacao_a, int(test_id[:6]), f'1{test_id}'[:9])
            self.id_quota_a = create_test_quota(cursor, self.id_associacao_a, 30.00, 'Mensal')

    def test_migration11_functions_exist(self):
        """Verificar se as funções da migração 11 foram criadas."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_proc WHERE proname = 'identificar_inconsistencias_quotas'")
            self.assertIsNotNone(cursor.fetchone(), "Função identificar_inconsistencias_quotas não existe")

            cursor.execute("SELECT 1 FROM pg_proc WHERE proname = 'recalcular_estados_quotas_associado'")
            self.assertIsNotNone(cursor.fetchone(), "Procedure recalcular_estados_quotas_associado não existe")

    def test_migration11_recalcula_estados_inconsistentes(self):
        """Testar que a migração recalcula estados inconsistentes."""
        with connection.cursor() as cursor:
            # Criar quota com estado inconsistente (diz 'Pago' mas sem pagamentos)
            id_qa = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pago', '01/2025')

            # Verificar que está inconsistente
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pago')

            total_pago = get_pagamentos_total(cursor, id_qa)
            self.assertEqual(total_pago, Decimal('0.00'))

            # Chamar a função de identificação
            cursor.execute("SELECT * FROM identificar_inconsistencias_quotas(%s)", [self.id_associacao_a])
            inconsistencias = cursor.fetchall()
            self.assertEqual(len(inconsistencias), 1)
            self.assertEqual(inconsistencias[0][0], id_qa)
            self.assertEqual(inconsistencias[0][2], 'Pago')  # estado_atual
            self.assertEqual(inconsistencias[0][3], 'Pendente')  # estado_calculado (sem pagamentos, vencimento futuro)

            # Executar recálculo
            cursor.execute("CALL recalcular_estados_quotas_associado(%s)", [self.id_associacao_a])

            # Verificar que foi corrigido
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pendente')

            # Verificar que não há mais inconsistências
            cursor.execute("SELECT * FROM identificar_inconsistencias_quotas(%s)", [self.id_associacao_a])
            inconsistencias = cursor.fetchall()
            self.assertEqual(len(inconsistencias), 0)

    def test_migration11_preserva_isento(self):
        """Testar que estado 'Isento' é preservado."""
        with connection.cursor() as cursor:
            # Criar quota isenta
            id_qa = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Isento', '01/2025')

            # Adicionar pagamento (não deveria acontecer na prática, mas testar a migração)
            cursor.execute("""
                INSERT INTO pagamento (data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado)
                VALUES (%s, %s, %s, %s, %s)
            """, [date.today(), Decimal('30.00'), 'Dinheiro', 'TESTE', id_qa])

            # Verificar estado atual é Isento
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Isento')

            # Executar recálculo
            cursor.execute("CALL recalcular_estados_quotas_associado(%s)", [self.id_associacao_a])

            # Verificar que continua Isento
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Isento')

    def test_migration11_idempotente(self):
        """Testar que a migração é idempotente (pode ser executada múltiplas vezes)."""
        with connection.cursor() as cursor:
            # Criar quota com estado inconsistente
            id_qa = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pago', '01/2025')

            # Executar recálculo primeira vez
            cursor.execute("CALL recalcular_estados_quotas_associado(%s)", [self.id_associacao_a])
            estado1 = get_quota_associado_estado(cursor, id_qa)

            # Executar recálculo segunda vez
            cursor.execute("CALL recalcular_estados_quotas_associado(%s)", [self.id_associacao_a])
            estado2 = get_quota_associado_estado(cursor, id_qa)

            # Executar recálculo terceira vez
            cursor.execute("CALL recalcular_estados_quotas_associado(%s)", [self.id_associacao_a])
            estado3 = get_quota_associado_estado(cursor, id_qa)

            # Estado deve ser o mesmo e correto
            self.assertEqual(estado1, 'Pendente')
            self.assertEqual(estado2, 'Pendente')
            self.assertEqual(estado3, 'Pendente')

    def test_migration11_identifica_inconsistencias_corretamente(self):
        """Testar que a função identificar_inconsistencias_quotas funciona corretamente."""
        with connection.cursor() as cursor:
            # Quota 1: Estado correto (Pendente, sem pagamentos, vencimento futuro)
            id_qa1 = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Quota 2: Estado inconsistente (Pago sem pagamentos)
            id_qa2 = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pago', '02/2025')

            # Quota 3: Estado inconsistente (Pendente mas vencida)
            id_qa3 = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '03/2025')
            cursor.execute("UPDATE quota_associado SET data_vencimento = %s WHERE id_quota_associado = %s",
                          [date.today() - timedelta(days=30), id_qa3])
            # Trigger AFTER UPDATE deve ter recalculado para 'Em Dívida'

            # Quota 4: Isento (sempre consistente)
            id_qa4 = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Isento', '04/2025')

            # Verificar inconsistências
            cursor.execute("SELECT * FROM identificar_inconsistencias_quotas(%s)", [self.id_associacao_a])
            inconsistencias = cursor.fetchall()

            # Deve encontrar apenas a quota 2 (Pago sem pagamentos)
            # Quota 3 pode ter sido corrigida pelo trigger
            # Quota 1 e 4 estão consistentes
            ids_inconsistentes = [row[0] for row in inconsistencias]
            self.assertIn(id_qa2, ids_inconsistentes)

            # Verificar detalhes da inconsistência
            for row in inconsistencias:
                if row[0] == id_qa2:
                    self.assertEqual(row[2], 'Pago')  # estado_atual
                    self.assertEqual(row[3], 'Pendente')  # estado_calculado

    def test_migration11_recalcula_multiplas_associacoes(self):
        """Testar que a migração funciona para múltiplas associações."""
        with connection.cursor() as cursor:
            test_id = str(uuid.uuid4().int)[:8]
            nipc_b = f'2{test_id}'[:9]
            id_associacao_b = create_test_associacao(cursor, nipc_b, f'Associação B {test_id}')
            id_associado_b1 = create_test_associado(cursor, id_associacao_b, int(test_id[:6]) + 1, f'2{test_id}'[:9])
            id_quota_b = create_test_quota(cursor, id_associacao_b, 50.00, 'Mensal')

            # Criar quota inconsistente na associação A
            id_qa_a = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pago', '01/2025')

            # Criar quota inconsistente na associação B
            id_qa_b = create_test_quota_associado(cursor, id_associado_b1, id_quota_b, 50.00, 'Pago', '01/2025')

            # Executar recálculo sem filtro (todas as associações)
            cursor.execute("CALL recalcular_estados_quotas_associado()")

            # Verificar que ambas foram corrigidas
            estado_a = get_quota_associado_estado(cursor, id_qa_a)
            estado_b = get_quota_associado_estado(cursor, id_qa_b)

            self.assertEqual(estado_a, 'Pendente')
            self.assertEqual(estado_b, 'Pendente')


if __name__ == '__main__':
    import unittest
    unittest.main()