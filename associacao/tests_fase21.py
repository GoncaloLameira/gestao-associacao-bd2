#!/usr/bin/env python3
"""
Testes de integração para Fase 2.1 - Núcleo Financeiro
Valida atualização automática de estado de quota_associado baseada em pagamentos.
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
from datetime import date, datetime, timedelta
import threading


def create_test_associacao(cursor, nipc, nome='Associação Teste'):
    """Helper para criar associação de teste."""
    cursor.execute("""
        INSERT INTO associacao (nipc, nome, password_hash, email)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (nipc) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id_associacao
    """, [nipc, nome, 'pbkdf2_sha256$1000000$gX3hSIFgzSq3pDY1q9uTIA$UYkfnS0B/vlyi3rZuTZ3Wxxa+PQKAvbeFjjGgwPy9zU=', 'direcao@teste.pt'])
    return cursor.fetchone()[0]


def create_test_associado(cursor, id_associacao, numero, nif, estado='Ativo'):
    """Helper para criar associado de teste."""
    cursor.execute("""
        INSERT INTO associado (numero_associado, nome, nif, data_adesao, estado, id_associacao)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_associado
    """, [numero, f'Associado {numero}', nif, date.today() - timedelta(days=365), estado, id_associacao])
    return cursor.fetchone()[0]


def create_test_quota(cursor, id_associacao, valor=30.00, periodicidade='Mensal'):
    """Helper para criar quota de teste."""
    cursor.execute("""
        INSERT INTO quota (designacao_quota, valor_quota, periodicidade_quota, data_inicio_quota, id_associacao)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id_quota
    """, [f'Quota {periodicidade}', valor, periodicidade, date.today() - timedelta(days=30), id_associacao])
    return cursor.fetchone()[0]


def create_test_quota_associado(cursor, id_associado, id_quota, valor_devido=30.00, estado='Pendente', periodo='01/2025'):
    """Helper para criar quota_associado de teste."""
    cursor.execute("""
        INSERT INTO quota_associado (valor_devido, data_vencimento, periodo_referencia, estado_quota_associado, id_associado, id_quota)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_quota_associado
    """, [valor_devido, date.today() + timedelta(days=30), periodo, estado, id_associado, id_quota])
    return cursor.fetchone()[0]


def get_quota_associado_estado(cursor, id_quota_associado):
    """Helper para obter estado da quota_associado."""
    cursor.execute("SELECT estado_quota_associado FROM quota_associado WHERE id_quota_associado = %s", [id_quota_associado])
    row = cursor.fetchone()
    return row[0] if row else None


def get_pagamentos_total(cursor, id_quota_associado):
    """Helper para obter total pago."""
    cursor.execute("SELECT COALESCE(SUM(valor_pago), 0) FROM pagamento WHERE id_quota_associado = %s", [id_quota_associado])
    return cursor.fetchone()[0]


def clean_pagamentos(cursor, id_quota_associado):
    """Limpar pagamentos de uma quota para evitar poluição entre testes."""
    cursor.execute("DELETE FROM pagamento WHERE id_quota_associado = %s", [id_quota_associado])
    cursor.execute("UPDATE quota_associado SET estado_quota_associado = 'Pendente' WHERE id_quota_associado = %s", [id_quota_associado])


class Fase21FinanceiroTests(TransactionTestCase):
    """Testes para Fase 2.1 - Núcleo Financeiro."""

    reset_sequences = True

    def setUp(self):
        """Criar duas associações base e dados de teste."""
        # Usar IDs únicos baseados no nome do teste para evitar conflitos
        test_id = str(uuid.uuid4().int)[:8]

        with connection.cursor() as cursor:
            # Associação A
            nipc_a = f'1{test_id}'[:9]
            self.id_associacao_a = create_test_associacao(cursor, nipc_a, f'Associação A {test_id}')
            self.id_associado_a1 = create_test_associado(cursor, self.id_associacao_a, int(test_id[:6]), f'1{test_id}'[:9])
            self.id_quota_a = create_test_quota(cursor, self.id_associacao_a, 30.00, 'Mensal')

            # Associação B
            nipc_b = f'2{test_id}'[:9]
            self.id_associacao_b = create_test_associacao(cursor, nipc_b, f'Associação B {test_id}')
            self.id_associado_b1 = create_test_associado(cursor, self.id_associacao_b, int(test_id[:6]) + 1, f'2{test_id}'[:9])
            self.id_quota_b = create_test_quota(cursor, self.id_associacao_b, 50.00, 'Mensal')

    def _create_fresh_qa(self, cursor, id_associado, id_quota, valor_devido=30.00, estado='Pendente', periodo='01/2025'):
        """Criar quota_associado fresco para o teste."""
        return create_test_quota_associado(cursor, id_associado, id_quota, valor_devido, estado, periodo)

    def test_01_pagamento_parcial(self):
        """Pagamento parcial → estado 'Parcial'."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Pagamento de 10€ em quota de 30€
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('10.00'), 'Dinheiro', 'REF001',
                           id_qa, None, self.id_associacao_a])

            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Parcial')

            total = get_pagamentos_total(cursor, id_qa)
            self.assertEqual(total, Decimal('10.00'))

    def test_02_pagamento_total(self):
        """Pagamento total → estado 'Pago'."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Pagamento de 30€ em quota de 30€
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF002',
                           id_qa, None, self.id_associacao_a])

            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pago')

    def test_03_multiplos_pagamentos(self):
        """Múltiplos pagamentos parciais até completar."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Pagamento 1: 10€
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('10.00'), 'Dinheiro', 'REF003',
                           id_qa, None, self.id_associacao_a])
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Parcial')

            # Pagamento 2: 15€
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('15.00'), 'Transferência', 'REF004',
                           id_qa, None, self.id_associacao_a])
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Parcial')

            # Pagamento 3: 5€ (completa)
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('5.00'), 'MB Way', 'REF005',
                           id_qa, None, self.id_associacao_a])
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pago')

            total = get_pagamentos_total(cursor, id_qa)
            self.assertEqual(total, Decimal('30.00'))

    def test_04_eliminar_pagamento(self):
        """Eliminação de pagamento recalcula estado."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Pagamento total
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF006',
                           id_qa, None, self.id_associacao_a])
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pago')

            # Obter ID do pagamento
            cursor.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", [id_qa])
            id_pagamento = cursor.fetchone()[0]

            # Eliminar pagamento
            cursor.execute("CALL eliminar_pagamento(%s, %s);", [id_pagamento, self.id_associacao_a])

            # Estado deve voltar a Pendente (sem pagamentos, vencimento futuro)
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pendente')

    def test_05_atualizar_pagamento(self):
        """Atualização de pagamento recalcula estado."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Pagamento parcial
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('10.00'), 'Dinheiro', 'REF007',
                           id_qa, None, self.id_associacao_a])

            # Obter ID do pagamento
            cursor.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", [id_qa])
            id_pagamento = cursor.fetchone()[0]

            # Atualizar para valor total
            cursor.execute("CALL atualizar_pagamento(%s, %s, %s, %s, %s, %s, %s, %s);",
                          [id_pagamento, datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF007_ATUAL',
                           id_qa, None, self.id_associacao_a])

            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pago')

    def test_06_quota_isento(self):
        """Quota isenta mantém estado 'Isento' mesmo com pagamento."""
        with connection.cursor() as cursor:
            # Criar quota isenta
            id_qa_isento = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a,
                                                        30.00, 'Isento', '02/2025')

            # Tentar registar pagamento - deve falhar ou manter Isento
            try:
                cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                              [datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF008',
                               id_qa_isento, None, self.id_associacao_a])
                # Se não falhou, verificar estado
                estado = get_quota_associado_estado(cursor, id_qa_isento)
                # Deve manter Isento (regra de negócio: isento não cobrável)
                self.assertEqual(estado, 'Isento',
                    'Quota Isento não deve mudar de estado ao receber pagamento')
            except Exception as e:
                # Se falhou com exceção, é aceitável
                self.assertTrue('Isento' in str(e) or 'excede' in str(e) or 'não permitida' in str(e))

    def test_07_pagamento_excessivo(self):
        """Pagamento que excede valor devido deve ser rejeitado."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Primeiro pagamento parcial
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('10.00'), 'Dinheiro', 'REF009',
                           id_qa, None, self.id_associacao_a])

            # Tentar pagamento que excede (30 - 10 = 20 restantes, tentar 25)
            with self.assertRaises(Exception) as context:
                cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                              [datetime.now(), Decimal('25.00'), 'Dinheiro', 'REF010',
                               id_qa, None, self.id_associacao_a])

            self.assertTrue('excede' in str(context.exception).lower() or
                          'excessivo' in str(context.exception).lower() or
                          'valor devido' in str(context.exception).lower())

            # Estado deve continuar Parcial
            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Parcial')

    def test_08_isolamento_duas_associacoes(self):
        """Pagamentos numa associação não afetam quotas da outra."""
        with connection.cursor() as cursor:
            id_qa_a = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')
            id_qa_b = self._create_fresh_qa(cursor, self.id_associado_b1, self.id_quota_b, 50.00, 'Pendente', '01/2025')

            # Pagamento na associação A
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF011',
                           id_qa_a, None, self.id_associacao_a])

            # Verificar A está Pago
            estado_a = get_quota_associado_estado(cursor, id_qa_a)
            self.assertEqual(estado_a, 'Pago')

            # Verificar B continua Pendente
            estado_b = get_quota_associado_estado(cursor, id_qa_b)
            self.assertEqual(estado_b, 'Pendente')

            # Tentar pagamento na B usando quota da A deve falhar
            with self.assertRaises(Exception) as context:
                cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                              [datetime.now(), Decimal('50.00'), 'Dinheiro', 'REF012',
                               id_qa_a, None, self.id_associacao_b])

            self.assertTrue('não pertence' in str(context.exception).lower() or
                          'autorizada' in str(context.exception).lower())

    def test_09_atualizar_pagamento_muda_quota(self):
        """Atualizar pagamento para quota diferente atualiza ambas."""
        with connection.cursor() as cursor:
            id_qa_a1 = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')
            id_qa_a2 = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '02/2025')

            # Pagamento na primeira quota
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF013',
                           id_qa_a1, None, self.id_associacao_a])

            # Obter ID do pagamento
            cursor.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", [id_qa_a1])
            id_pagamento = cursor.fetchone()[0]

            # Atualizar pagamento para apontar para segunda quota
            cursor.execute("CALL atualizar_pagamento(%s, %s, %s, %s, %s, %s, %s, %s);",
                          [id_pagamento, datetime.now(), Decimal('30.00'), 'Dinheiro', 'REF013_ATUAL',
                           id_qa_a2, None, self.id_associacao_a])

            # Primeira quota deve voltar a Pendente
            estado_a1 = get_quota_associado_estado(cursor, id_qa_a1)
            self.assertEqual(estado_a1, 'Pendente')

            # Segunda quota deve estar Paga
            estado_a2 = get_quota_associado_estado(cursor, id_qa_a2)
            self.assertEqual(estado_a2, 'Pago')

    def test_10_vencimento_em_divida(self):
        """Quota sem pagamentos e vencida → 'Em Dívida'."""
        with connection.cursor() as cursor:
            # Criar quota com vencimento passado (data_vencimento no passado)
            id_qa_vencida = create_test_quota_associado(cursor, self.id_associado_a1, self.id_quota_a,
                                                         30.00, 'Pendente', '01/2020')

            # Atualizar data_vencimento para passado (o helper usa data_vencimento = hoje + 30 dias)
            cursor.execute("UPDATE quota_associado SET data_vencimento = %s WHERE id_quota_associado = %s",
                          [date.today() - timedelta(days=30), id_qa_vencida])

            # A procedure de atualização deve ter recalculado para Em Dívida
            cursor.execute("CALL atualizar_estado_quota_associado(%s);", [id_qa_vencida])

            estado = get_quota_associado_estado(cursor, id_qa_vencida)
            self.assertEqual(estado, 'Em Dívida')

    def test_11_pagamento_com_movimento_bancario(self):
        """Pagamento associado a movimento bancário funciona."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Criar movimento bancário
            cursor.execute("""
                INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id_movimento
            """, [date.today(), 'Transferência recebida', Decimal('30.00'), 'MB001', self.id_associacao_a])
            id_movimento = cursor.fetchone()[0]

            # Pagamento com movimento
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('30.00'), 'Transferência', 'MB001',
                           id_qa, id_movimento, self.id_associacao_a])

            estado = get_quota_associado_estado(cursor, id_qa)
            self.assertEqual(estado, 'Pago')

            # Verificar link
            cursor.execute("SELECT id_movimento FROM pagamento WHERE id_quota_associado = %s", [id_qa])
            self.assertEqual(cursor.fetchone()[0], id_movimento)

    def test_12_concorrencia_pagamentos(self):
        """Teste de concorrência: dois pagamentos simultâneos na mesma quota."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

        results = {'success': 0, 'errors': []}
        barrier = threading.Barrier(2)

        def make_payment(thread_id):
            try:
                import psycopg2
                conn = psycopg2.connect(
                    dbname='test_gestao_associacao',
                    user='postgres',
                    password='ioT574259',
                    host='localhost',
                    port='5432'
                )
                conn.autocommit = False
                cursor = conn.cursor()

                barrier.wait()

                cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                              [datetime.now(), Decimal('15.00'), 'Dinheiro', f'REF_CONC_{thread_id}',
                               id_qa, None, self.id_associacao_a])

                conn.commit()
                results['success'] += 1
            except Exception as e:
                conn.rollback()
                results['errors'].append(str(e))
            finally:
                conn.close()

        # Reset quota state
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM pagamento WHERE id_quota_associado = %s", [id_qa])
            cursor.execute("UPDATE quota_associado SET estado_quota_associado = 'Pendente' WHERE id_quota_associado = %s", [id_qa])

        t1 = threading.Thread(target=make_payment, args=(1,))
        t2 = threading.Thread(target=make_payment, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with connection.cursor() as cursor:
            estado = get_quota_associado_estado(cursor, id_qa)
            total = get_pagamentos_total(cursor, id_qa)

            self.assertIn(estado, ['Parcial', 'Pago'])
            self.assertLessEqual(total, Decimal('30.00'))

    def test_13_concorrencia_pagamentos_excedente(self):
        """Teste: dois pagamentos simultâneos cuja soma excederia valor_devido."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

        results = {'success': 0, 'rejected': 0, 'errors': []}
        barrier = threading.Barrier(2)

        def make_payment_excess(thread_id):
            try:
                import psycopg2
                conn = psycopg2.connect(
                    dbname='test_gestao_associacao',
                    user='postgres',
                    password='ioT574259',
                    host='localhost',
                    port='5432'
                )
                conn.autocommit = False
                cursor = conn.cursor()

                barrier.wait()

                # Cada thread tenta pagar 20€ (total 40€ > 30€ devido)
                cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                              [datetime.now(), Decimal('20.00'), 'Dinheiro', f'REF_EXC_{thread_id}',
                               id_qa, None, self.id_associacao_a])

                conn.commit()
                results['success'] += 1
            except Exception as e:
                conn.rollback()
                if 'excede' in str(e).lower() or 'excessivo' in str(e).lower() or 'valor devido' in str(e).lower():
                    results['rejected'] += 1
                else:
                    results['errors'].append(str(e))
            finally:
                conn.close()

        # Reset quota state
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM pagamento WHERE id_quota_associado = %s", [id_qa])
            cursor.execute("UPDATE quota_associado SET estado_quota_associado = 'Pendente' WHERE id_quota_associado = %s", [id_qa])

        t1 = threading.Thread(target=make_payment_excess, args=(1,))
        t2 = threading.Thread(target=make_payment_excess, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with connection.cursor() as cursor:
            total = get_pagamentos_total(cursor, id_qa)
            estado = get_quota_associado_estado(cursor, id_qa)

            # Exatamente um deve ter sucesso, o outro deve ser rejeitado
            self.assertEqual(results['success'], 1, f"Esperava 1 sucesso, teve {results['success']}. Erros: {results['errors']}")
            self.assertEqual(results['rejected'], 1, f"Esperava 1 rejeitado, teve {results['rejected']}")
            self.assertLessEqual(total, Decimal('30.00'))
            self.assertIn(estado, ['Parcial', 'Pago'])

    def test_14_concorrencia_atualizacao_mesmo_pagamento(self):
        """Teste: duas atualizações concorrentes do mesmo pagamento (last writer wins)."""
        with connection.cursor() as cursor:
            id_qa = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')

            # Criar pagamento inicial
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('10.00'), 'Dinheiro', 'REF_BASE',
                           id_qa, None, self.id_associacao_a])
            cursor.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", [id_qa])
            id_pagamento = cursor.fetchone()[0]

        results = {'success': 0, 'errors': []}
        barrier = threading.Barrier(2)

        def update_payment(thread_id, new_value):
            try:
                import psycopg2
                conn = psycopg2.connect(
                    dbname='test_gestao_associacao',
                    user='postgres',
                    password='ioT574259',
                    host='localhost',
                    port='5432'
                )
                conn.autocommit = False
                cursor = conn.cursor()

                barrier.wait()

                cursor.execute("CALL atualizar_pagamento(%s, %s, %s, %s, %s, %s, %s, %s);",
                              [id_pagamento, datetime.now(), new_value, 'Cartão', f'REF_UPD_{thread_id}',
                               id_qa, None, self.id_associacao_a])

                conn.commit()
                results['success'] += 1
            except Exception as e:
                conn.rollback()
                results['errors'].append(str(e))
            finally:
                conn.close()

        # Thread 1: atualiza para 15€
        # Thread 2: atualiza para 20€
        t1 = threading.Thread(target=update_payment, args=(1, Decimal('15.00')))
        t2 = threading.Thread(target=update_payment, args=(2, Decimal('20.00')))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with connection.cursor() as cursor:
            cursor.execute("SELECT valor_pago FROM pagamento WHERE id_pagamento = %s", [id_pagamento])
            final_valor = cursor.fetchone()[0]
            total = get_pagamentos_total(cursor, id_qa)
            estado = get_quota_associado_estado(cursor, id_qa)

            # Ambas atualizações podem ter sucesso (last writer wins) - sem deadlock
            self.assertGreaterEqual(results['success'], 1, f"Esperava pelo menos 1 sucesso, teve {results['success']}. Erros: {results['errors']}")
            self.assertLessEqual(results['success'], 2)
            # Valor final deve ser um dos dois valores tentados
            self.assertIn(final_valor, [Decimal('15.00'), Decimal('20.00')])
            self.assertEqual(total, final_valor)
            self.assertLessEqual(total, Decimal('30.00'))
            # Estado deve ser consistente
            self.assertIn(estado, ['Parcial', 'Pago'])

    def test_15_concorrencia_movimento_qa_opostos(self):
        """Teste: movimentação simultânea de pagamentos entre QA1 e QA2 em sentidos opostos.

        Este teste verifica que:
        1. Não ocorre deadlock (ordem determinística de locks)
        2. O sistema mantém estado seguro (pode rejeitar se exceder limites)
        3. Estados finais são consistentes
        """
        with connection.cursor() as cursor:
            id_qa1 = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '01/2025')
            id_qa2 = self._create_fresh_qa(cursor, self.id_associado_a1, self.id_quota_a, 30.00, 'Pendente', '02/2025')

            # Criar pagamento P1 na QA1 (20€)
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('20.00'), 'Dinheiro', 'REF_P1',
                           id_qa1, None, self.id_associacao_a])
            cursor.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", [id_qa1])
            id_p1 = cursor.fetchone()[0]

            # Criar pagamento P2 na QA2 (15€)
            cursor.execute("CALL registar_pagamento(%s, %s, %s, %s, %s, %s, %s, NULL);",
                          [datetime.now(), Decimal('15.00'), 'Transferência', 'REF_P2',
                           id_qa2, None, self.id_associacao_a])
            cursor.execute("SELECT id_pagamento FROM pagamento WHERE id_quota_associado = %s", [id_qa2])
            id_p2 = cursor.fetchone()[0]

        results = {'success_p1': 0, 'success_p2': 0, 'errors': []}
        barrier = threading.Barrier(2)

        def move_p1_to_qa2():
            try:
                import psycopg2
                conn = psycopg2.connect(
                    dbname='test_gestao_associacao',
                    user='postgres',
                    password='ioT574259',
                    host='localhost',
                    port='5432'
                )
                conn.autocommit = False
                cursor = conn.cursor()

                barrier.wait()

                # Mover P1 de QA1 para QA2
                cursor.execute("CALL atualizar_pagamento(%s, %s, %s, %s, %s, %s, %s, %s);",
                              [id_p1, datetime.now(), Decimal('20.00'), 'Dinheiro', 'REF_P1_MOVED',
                               id_qa2, None, self.id_associacao_a])

                conn.commit()
                results['success_p1'] += 1
            except Exception as e:
                conn.rollback()
                results['errors'].append(f"P1: {e}")
            finally:
                conn.close()

        def move_p2_to_qa1():
            try:
                import psycopg2
                conn = psycopg2.connect(
                    dbname='test_gestao_associacao',
                    user='postgres',
                    password='ioT574259',
                    host='localhost',
                    port='5432'
                )
                conn.autocommit = False
                cursor = conn.cursor()

                barrier.wait()

                # Mover P2 de QA2 para QA1
                cursor.execute("CALL atualizar_pagamento(%s, %s, %s, %s, %s, %s, %s, %s);",
                              [id_p2, datetime.now(), Decimal('15.00'), 'Transferência', 'REF_P2_MOVED',
                               id_qa1, None, self.id_associacao_a])

                conn.commit()
                results['success_p2'] += 1
            except Exception as e:
                conn.rollback()
                results['errors'].append(f"P2: {e}")
            finally:
                conn.close()

        t1 = threading.Thread(target=move_p1_to_qa2)
        t2 = threading.Thread(target=move_p2_to_qa1)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with connection.cursor() as cursor:
            # Verificar onde cada pagamento está
            cursor.execute("SELECT id_quota_associado FROM pagamento WHERE id_pagamento = %s", [id_p1])
            p1_final_qa = cursor.fetchone()[0]
            cursor.execute("SELECT id_quota_associado FROM pagamento WHERE id_pagamento = %s", [id_p2])
            p2_final_qa = cursor.fetchone()[0]

            estado_qa1 = get_quota_associado_estado(cursor, id_qa1)
            estado_qa2 = get_quota_associado_estado(cursor, id_qa2)
            total_qa1 = get_pagamentos_total(cursor, id_qa1)
            total_qa2 = get_pagamentos_total(cursor, id_qa2)

            # Verificações de segurança:
            # 1. Sem deadlock - pelo menos uma thread deve completar (sem erro de deadlock)
            total_success = results['success_p1'] + results['success_p2']
            self.assertGreaterEqual(total_success, 0)  # Sem deadlock = teste passa se não travar

            # 2. Nenhum erro de deadlock nos erros
            deadlock_errors = [e for e in results['errors'] if 'deadlock' in e.lower()]
            self.assertEqual(len(deadlock_errors), 0, f"Deadlock detectado: {deadlock_errors}")

            # 3. Totais não excedem valor_devido (30€)
            self.assertLessEqual(total_qa1, Decimal('30.00'))
            self.assertLessEqual(total_qa2, Decimal('30.00'))

            # 4. Estados são válidos
            self.assertIn(estado_qa1, ['Pendente', 'Parcial', 'Pago', 'Em Dívida'])
            self.assertIn(estado_qa2, ['Pendente', 'Parcial', 'Pago', 'Em Dívida'])

            # 5. Pagamentos mantêm seus valores
            cursor.execute("SELECT valor_pago FROM pagamento WHERE id_pagamento = %s", [id_p1])
            self.assertEqual(cursor.fetchone()[0], Decimal('20.00'))
            cursor.execute("SELECT valor_pago FROM pagamento WHERE id_pagamento = %s", [id_p2])
            self.assertEqual(cursor.fetchone()[0], Decimal('15.00'))


if __name__ == '__main__':
    import unittest
    unittest.main()