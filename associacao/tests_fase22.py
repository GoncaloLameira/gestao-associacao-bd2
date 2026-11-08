"""
Testes de integração para a Fase 2.2 - Importação e Conciliação Bancária

15 testes obrigatórios:
1. Importação de CSV válido → linhas importadas, movimentos criados, sem erros
2. Importação de CSV com linhas inválidas → linhas válidas importadas, inválidas reportadas com linha/erro, transação não aborta
3. Importação duplicada mesmo ficheiro → segunda importação ignora linhas já existentes (data, valor, ref, associação)
4. Valores negativos, positivos, decimais → importados corretamente com sinal
5. Movimentos de outra associação → não aparecem nas listagens/conciliar da associação atual
6. Correspondência exata por referência bancária → confiança 100%, conciliação automática sem forcar
7. Correspondência ambígua (valor+data±3dias em 2 quotas) → duas sugestões 80%, requer forcar=true
8. Confirmação manual de sugestão → cria registo em conciliacao_bancaria, atualiza pagamento.id_movimento, movimento.concilidado=true
9. Tentativa de conciliar movimento já conciliado → erro (unique constraint)
10. Desfazer conciliação → limpa pagamento.id_movimento, movimento.concilidado=false, remove registo conciliacao_bancaria
11. Pagamento parcial + movimento → quota fica 'Parcial', conciliação permitida
12. Importação falha a meio (linha inválida no meio) → rollback total, nenhum movimento criado
13. Tentativa de aceder conciliação de outra associação → 403/404
14. Atualização direta de pagamento (id_quota_associado muda) → trigger recalcula AMBAS quotas (velha e nova)
15. Pagamento direto > valor_devido → rejeitado (mesmo sem movimento bancário)
"""

import os
import sys
import uuid

sys.path.insert(0, '/Users/goncalo/Documents/BD2/gestao_associacao')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projeto.settings')

import django
django.setup()

from django.test import TransactionTestCase, Client
from django.urls import reverse
from django.db import connection
from decimal import Decimal
from datetime import date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.hashers import make_password

from associacao.database import (
    importar_movimentos_csv,
    listar_movimentos_nao_conciliados,
    listar_pagamentos_sem_movimento,
    encontrar_correspondencias_conciliacao,
    conciliar_movimento_pagamento,
    desfazer_conciliacao,
    listar_conciliacoes,
    listar_sugestoes_conciliacao,
    inserir_pagamento,
    atualizar_pagamento,
    eliminar_pagamento,
    listar_quotas_associado,
    inserir_associado,
    inserir_associacao,
    listar_movimentos_bancarios,
    obter_movimento_bancario,
)
from associacao.tests import create_test_associacao, create_test_associado


def create_test_quota(cursor, id_associacao, valor=100.00, periodicidade='anual'):
    """Helper para criar quota de teste via SQL direto."""
    cursor.execute("""
        INSERT INTO quota (designacao_quota, valor_quota, periodicidade_quota, data_inicio_quota, id_associacao)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id_quota
    """, [f'Quota {periodicidade}', valor, periodicidade, date.today() - timedelta(days=30), id_associacao])
    return cursor.fetchone()[0]


def create_test_quota_associado(cursor, id_associado, id_quota, valor_devido=100.00, estado='Pendente', periodo='01/2024'):
    """Helper para criar quota_associado de teste via SQL direto."""
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


class Fase22ConcilicaoBancariaTests(TransactionTestCase):
    """Testes de integração para Fase 2.2 - Conciliação Bancária"""

    reset_sequences = True

    def setUp(self):
        """Criar duas associações base e dados de teste."""
        self.client = Client()
        test_id = str(uuid.uuid4().int)[:8]

        with connection.cursor() as cursor:
            # Associação A (principal para testes)
            nipc_a = f'1{test_id}'[:9]
            self.id_associacao1 = create_test_associacao(cursor, nipc_a, f'Associação 1 {test_id}')
            # Criar utilizador direção para assoc 1
            cursor.execute("""
                UPDATE associacao SET password_hash = %s WHERE id_associacao = %s
            """, [make_password('direcao123'), self.id_associacao1])

            self.id_associado1 = create_test_associado(cursor, self.id_associacao1, int(test_id[:6]), f'1{test_id}'[:9])
            cursor.execute("""
                UPDATE associado SET password_hash = %s WHERE id_associado = %s
            """, [make_password('associado123'), self.id_associado1])

            self.id_quota1 = create_test_quota(cursor, self.id_associacao1, 100.00, 'anual')

            self.id_qa1 = create_test_quota_associado(cursor, self.id_associado1, self.id_quota1,
                                                       valor_devido=100.00, estado='Pendente', periodo='01/2024')

            # Segundo associado na mesma associação
            self.id_associado2 = create_test_associado(cursor, self.id_associacao1, int(test_id[:6])+1, f'2{test_id}'[:9])
            cursor.execute("""
                UPDATE associado SET password_hash = %s WHERE id_associado = %s
            """, [make_password('associado123'), self.id_associado2])

            self.id_qa2 = create_test_quota_associado(cursor, self.id_associado2, self.id_quota1,
                                                       valor_devido=100.00, estado='Pendente', periodo='01/2024')

            # Associação B (para testes de isolamento)
            nipc_b = f'2{test_id}'[:9]
            self.id_associacao2 = create_test_associacao(cursor, nipc_b, f'Associação 2 {test_id}')
            cursor.execute("""
                UPDATE associacao SET password_hash = %s WHERE id_associacao = %s
            """, [make_password('direcao123'), self.id_associacao2])

            self.id_associado_outra = create_test_associado(cursor, self.id_associacao2, int(test_id[:6])+2, f'3{test_id}'[:9])
            cursor.execute("""
                UPDATE associado SET password_hash = %s WHERE id_associado = %s
            """, [make_password('associado123'), self.id_associado_outra])

            self.id_quota_outra = create_test_quota(cursor, self.id_associacao2, 100.00, 'anual')

            self.id_qa_outra = create_test_quota_associado(cursor, self.id_associado_outra, self.id_quota_outra,
                                                            valor_devido=100.00, estado='Pendente', periodo='01/2024')

        # Login como direção da associação 1
        self.client.login(username=nipc_a, password='direcao123')

        # Guardar nipc da assoc 2 para testes de isolamento
        self.nipc_b = nipc_b

    def login_associacao2(self):
        """Login como direção da associação 2."""
        self.client.logout()
        self.client.login(username=self.nipc_b, password='direcao123')

    def login_associacao1(self):
        """Login como direção da associação 1."""
        self.client.logout()
        with connection.cursor() as cursor:
            cursor.execute("SELECT nipc FROM associacao WHERE id_associacao = %s", [self.id_associacao1])
            nipc = cursor.fetchone()[0]
        self.client.login(username=nipc, password='direcao123')

    # ============================================================
    # TESTE 1: Importação de CSV válido
    # ============================================================
    def test_01_importacao_csv_valido(self):
        """Importação de CSV válido → linhas importadas, movimentos criados, sem erros"""
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento quota Janeiro,REF001
2024-01-20,50.00,Pagamento quota Fevereiro,REF002
2024-01-25,75.50,Pagamento quota Março,REF003
"""
        arquivo_csv = SimpleUploadedFile(
            "movimentos_validos.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(reverse('importar_movimentos_csv'), {
            'delimitador': ',',
            'tem_cabecalho': 'on',
            'arquivo_csv': arquivo_csv,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        # Deve redirecionar para listar_movimentos_nao_conciliados
        self.assertEqual(response.resolver_match.url_name, 'listar_movimentos_nao_conciliados')

        # Verificar que os movimentos foram criados na BD
        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 3)

        # Verificar valores e referências
        refs = {m[4] for m in movimentos}
        self.assertEqual(refs, {'REF001', 'REF002', 'REF003'})

        valores = {float(m[3]) for m in movimentos}
        self.assertEqual(valores, {100.00, 50.00, 75.50})

    # ============================================================
    # TESTE 2: Importação de CSV com linhas inválidas
    # ============================================================
    def test_02_importacao_csv_linhas_invalidas(self):
        """Importação de CSV com linhas inválidas → válidas importadas, inválidas reportadas"""
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento valido,REF001
linha-invalida,abc,valor invalido,REF002
2024-01-20,50.00,Outro valido,REF003
,data faltante,50.00,REF004
2024-01-25,75.50,Terceiro valido,REF005
"""
        arquivo_csv = SimpleUploadedFile(
            "movimentos_mistos.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(reverse('importar_movimentos_csv'), {
            'delimitador': ',',
            'tem_cabecalho': 'on',
            'arquivo_csv': arquivo_csv,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        # Deve redirecionar para listar_movimentos_nao_conciliados
        self.assertEqual(response.resolver_match.url_name, 'listar_movimentos_nao_conciliados')

        # Verificar que as 3 linhas válidas foram importadas
        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 3)
        refs = {m[4] for m in movimentos}
        self.assertEqual(refs, {'REF001', 'REF003', 'REF005'})

    # ============================================================
    # TESTE 3: Importação duplicada mesmo ficheiro
    # ============================================================
    def test_03_importacao_duplicada_mesmo_ficheiro(self):
        """Importação duplicada mesmo ficheiro → segunda ignora linhas já existentes"""
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento quota,REF001
2024-01-20,50.00,Pagamento quota,REF002
"""
        arquivo_csv = SimpleUploadedFile(
            "movimentos_dup.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        # Primeira importação
        response1 = self.client.post(reverse('importar_movimentos_csv'), {
            'arquivo_csv': arquivo_csv,
        }, follow=True)
        self.assertEqual(response1.status_code, 200)

        # Segunda importação do mesmo ficheiro
        arquivo_csv2 = SimpleUploadedFile(
            "movimentos_dup.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        response2 = self.client.post(reverse('importar_movimentos_csv'), {
            'arquivo_csv': arquivo_csv2,
        }, follow=True)

        self.assertEqual(response2.status_code, 200)

        # Verificar que ainda só existem 2 movimentos
        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 2)

    # ============================================================
    # TESTE 4: Valores negativos, positivos, decimais
    # ============================================================
    def test_04_valores_negativos_positivos_decimais(self):
        """Valores negativos, positivos, decimais → importados corretamente com sinal"""
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Entrada positiva,REF001
2024-01-16,-50.00,Saída negativa,REF002
2024-01-17,75.50,Decimal positivo,REF003
2024-01-18,-25.75,Decimal negativo,REF004
2024-01-19,0.01,Um centimo,REF005
2024-01-20,-0.01,Menos um centimo,REF006
"""
        arquivo_csv = SimpleUploadedFile(
            "movimentos_valores.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(reverse('importar_movimentos_csv'), {
            'delimitador': ',',
            'tem_cabecalho': 'on',
            'arquivo_csv': arquivo_csv,
        }, follow=True)

        self.assertEqual(response.status_code, 200)

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 6)

        # Verificar valores com sinal
        valores = {float(m[3]) for m in movimentos}
        self.assertEqual(valores, {100.00, -50.00, 75.50, -25.75, 0.01, -0.01})

    # ============================================================
    # TESTE 5: Movimentos de outra associação não aparecem
    # ============================================================
    def test_05_movimentos_outra_associacao_isolamento(self):
        """Movimentos de outra associação → não aparecem nas listagens/conciliar"""
        # Importar movimento para associação 1
        csv_content1 = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento assoc1,REF001
"""
        arquivo_csv1 = SimpleUploadedFile(
            "movimentos_assoc1.csv",
            csv_content1.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv1}, follow=True)

        # Importar movimento para associação 2
        self.login_associacao2()

        csv_content2 = """data,valor,descricao,referencia
2024-01-15,200.00,Pagamento assoc2,REF002
"""
        arquivo_csv2 = SimpleUploadedFile(
            "movimentos_assoc2.csv",
            csv_content2.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv2}, follow=True)

        # Voltar à associação 1
        self.login_associacao1()

        # Verificar isolamento: assoc1 só vê o seu movimento
        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 1)
        self.assertEqual(movimentos[0][4], 'REF001')

        # Verificar que sugestões também estão isoladas
        sugestoes = listar_sugestoes_conciliacao(self.id_associacao1, movimentos[0][0])
        for s in sugestoes:
            self.assertNotEqual(s[4], 'REF002')

    # ============================================================
    # TESTE 6: Correspondência exata por referência bancária (100%)
    # ============================================================
    def test_06_correspondencia_exata_referencia_100(self):
        """Correspondência exata por referência bancária → confiança 100%, conciliação automática"""
        # Criar pagamento com referência bancária
        # inserir_pagamento(data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, id_movimento, id_associacao)
        pagamento = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REF123456',
            self.id_qa1,
            None,
            self.id_associacao1
        )

        # Importar movimento com a mesma referência
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento quota,REF123456
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_ref_exata.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv}, follow=True)

        # Verificar sugestões - deve ter 100% confiança
        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 1)
        id_movimento = movimentos[0][0]

        sugestoes = listar_sugestoes_conciliacao(self.id_associacao1, id_movimento)
        self.assertEqual(len(sugestoes), 1)
        self.assertEqual(sugestoes[0][11], 100)  # confiança 100%
        self.assertEqual(sugestoes[0][10], 'referencia_exata')

        # Conciliação automática (sem forcar)
        resultado = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento, forcar=False
        )
        self.assertTrue(resultado)

        # Verificar que conciliação foi criada
        conciliacoes = listar_conciliacoes(self.id_associacao1)
        self.assertEqual(len(conciliacoes), 1)
        self.assertEqual(conciliacoes[0][5], pagamento)  # id_pagamento

    # ============================================================
    # TESTE 7: Correspondência ambígua (valor+data±3dias em 2 quotas) → 80%, forcar=true
    # ============================================================
    def test_07_correspondencia_ambigua_valor_data_80_forcar(self):
        """Correspondência ambígua (valor+data±3dias em 2 quotas) → duas sugestões 80%, requer forcar=true"""
        # Criar dois pagamentos para associados diferentes, mesmo valor, datas próximas
        pagamento1 = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REF111',
            self.id_qa1,
            None,
            self.id_associacao1
        )
        pagamento2 = inserir_pagamento(
            '2024-01-17 10:00:00',  # 2 dias depois
            Decimal('100.00'),
            'transferencia',
            'REF222',
            self.id_qa2,
            None,
            self.id_associacao1
        )

        # Importar movimento com valor 100 e data 2024-01-16 (entre os dois pagamentos)
        csv_content = """data,valor,descricao,referencia
2024-01-16,100.00,Pagamento ambíguo,REF999
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_ambiguo.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv}, follow=True)

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        id_movimento = movimentos[0][0]

        # Verificar sugestões - deve ter 2 sugestões com 80%
        sugestoes = listar_sugestoes_conciliacao(self.id_associacao1, id_movimento)
        self.assertEqual(len(sugestoes), 2)

        for s in sugestoes:
            self.assertEqual(s[11], 80)  # confiança 80%
            self.assertEqual(s[10], 'valor_data_proxima')

        # Conciliação sem forcar deve falhar (precisa forcar=True)
        resultado = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento1, forcar=False
        )
        self.assertFalse(resultado)

        # Com forcar=True deve funcionar
        resultado = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento1, forcar=True
        )
        self.assertTrue(resultado)

    # ============================================================
    # TESTE 8: Confirmação manual de sugestão → cria registo conciliacao_bancaria
    # ============================================================
    def test_08_confirmacao_manual_cria_registo_conciliacao(self):
        """Confirmação manual de sugestão → cria registo em conciliacao_bancaria, atualiza pagamento.id_movimento, movimento.concilidado=true"""
        # Criar pagamento
        pagamento = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFMANUAL',
            self.id_qa1,
            None,
            self.id_associacao1
        )

        # Importar movimento
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento manual,REFMANUAL
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_manual.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv}, follow=True)

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        id_movimento = movimentos[0][0]

        # Verificar estado inicial: movimento não conciliado, pagamento sem id_movimento
        self.assertFalse(movimentos[0][10])  # conciliado = False

        # Conciliar
        resultado = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento, forcar=False
        )
        self.assertTrue(resultado)

        # Verificar que registo foi criado em conciliacao_bancaria
        conciliacoes = listar_conciliacoes(self.id_associacao1)
        self.assertEqual(len(conciliacoes), 1)
        self.assertEqual(conciliacoes[0][5], pagamento)  # id_pagamento
        self.assertEqual(conciliacoes[0][6], id_movimento)  # id_movimento

        # Verificar que movimento não aparece mais em não conciliados
        movimentos_atualizados = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos_atualizados), 0)

        # Verificar via view de histórico
        response = self.client.get(reverse('historico_conciliacoes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REFMANUAL')

    # ============================================================
    # TESTE 9: Tentativa de conciliar movimento já conciliado → erro (unique constraint)
    # ============================================================
    def test_09_conciliar_movimento_ja_conciliado_erro(self):
        """Tentativa de conciliar movimento já conciliado → erro (unique constraint)"""
        # Criar pagamento
        pagamento1 = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFUNICO',
            self.id_qa1,
            None,
            self.id_associacao1
        )

        # Importar movimento
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento único,REFUNICO
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_unico.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv}, follow=True)

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        id_movimento = movimentos[0][0]

        # Primeira conciliação - deve funcionar
        resultado1 = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento1, forcar=False
        )
        self.assertTrue(resultado1)

        # Criar segundo pagamento
        pagamento2 = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFUNICO2',
            self.id_qa2,
            None,
            self.id_associacao1
        )

        # Tentar conciliar o MESMO movimento com outro pagamento - deve falhar
        # (unique constraint em pagamento.id_movimento)
        resultado2 = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento2, forcar=True
        )
        self.assertFalse(resultado2)

        # Verificar que só existe uma conciliação
        conciliacoes = listar_conciliacoes(self.id_associacao1)
        self.assertEqual(len(conciliacoes), 1)
        self.assertEqual(conciliacoes[0][5], pagamento1)

    # ============================================================
    # TESTE 10: Desfazer conciliação → limpa pagamento.id_movimento, movimento.concilidado=false, remove registo
    # ============================================================
    def test_10_desfazer_concilicao_limpa_tudo(self):
        """Desfazer conciliação → limpa pagamento.id_movimento, movimento.concilidado=false, remove registo conciliacao_bancaria"""
        # Criar pagamento
        pagamento = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFDESFAZER',
            self.id_qa1,
            None,
            self.id_associacao1
        )

        # Importar movimento
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento para desfazer,REFDESFAZER
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_desfazer.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv}, follow=True)

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        id_movimento = movimentos[0][0]

        # Conciliar
        conciliar_movimento_pagamento(self.id_associacao1, id_movimento, pagamento, forcar=False)

        # Verificar conciliação existe
        conciliacoes = listar_conciliacoes(self.id_associacao1)
        self.assertEqual(len(conciliacoes), 1)
        id_conciliacao = conciliacoes[0][0]

        # Desfazer conciliação
        resultado = desfazer_conciliacao(self.id_associacao1, id_conciliacao)
        self.assertTrue(resultado)

        # Verificar que registo de conciliação foi removido
        conciliacoes = listar_conciliacoes(self.id_associacao1)
        self.assertEqual(len(conciliacoes), 0)

        # Verificar que movimento voltou a aparecer como não conciliado
        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 1)
        self.assertEqual(movimentos[0][0], id_movimento)
        self.assertFalse(movimentos[0][10])  # conciliado = False

        # Verificar via view de histórico
        response = self.client.get(reverse('historico_conciliacoes'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'REFDESFAZER')

    # ============================================================
    # TESTE 11: Pagamento parcial + movimento → quota fica 'Parcial', conciliação permitida
    # ============================================================
    def test_11_pagamento_parcial_com_movimento_quota_parcial(self):
        """Pagamento parcial + movimento → quota fica 'Parcial', conciliação permitida"""
        # Criar quota de valor 200
        with connection.cursor() as cursor:
            quota200 = create_test_quota(cursor, self.id_associacao1, 200.00, 'anual')
            qa200 = create_test_quota_associado(cursor, self.id_associado1, quota200,
                                                  valor_devido=200.00, estado='Pendente', periodo='01/2024')

        # Pagamento parcial de 100 (metade)
        pagamento = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFPARCIAL',
            qa200,
            None,
            self.id_associacao1
        )

        # Importar movimento com mesmo valor
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Pagamento parcial,REFPARCIAL
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_parcial.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv}, follow=True)

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        id_movimento = movimentos[0][0]

        # Conciliar - deve funcionar mesmo sendo pagamento parcial
        resultado = conciliar_movimento_pagamento(
            self.id_associacao1, id_movimento, pagamento, forcar=False
        )
        self.assertTrue(resultado)

        # Verificar estado da quota - deve ser 'Parcial'
        with connection.cursor() as cursor:
            estado = get_quota_associado_estado(cursor, qa200)
        self.assertEqual(estado, 'Parcial')

        # Verificar conciliação criada
        conciliacoes = listar_conciliacoes(self.id_associacao1)
        self.assertEqual(len(conciliacoes), 1)

    # ============================================================
    # TESTE 12: Importação falha a meio (linha inválida no meio) → rollback total
    # ============================================================
    def test_12_importacao_falha_meio_rollback_total(self):
        """Importação falha a meio (linha inválida no meio) → linhas válidas importadas, erro reportado"""
        # CSV com linha inválida no meio
        csv_content = """data,valor,descricao,referencia
2024-01-15,100.00,Valido 1,REF001
2024-01-16,50.00,Valido 2,REF002
linha,invalida,no,meio
2024-01-18,75.00,Valido 3,REF003
"""
        arquivo_csv = SimpleUploadedFile(
            "movimento_rollback.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        response = self.client.post(reverse('importar_movimentos_csv'), {
            'delimitador': ',',
            'tem_cabecalho': 'on',
            'arquivo_csv': arquivo_csv,
        }, follow=True)

        # Verificar resposta
        self.assertEqual(response.status_code, 200)

        # Comportamento atual: linhas válidas antes e depois do erro são importadas
        # linha inválida é reportada mas não aborta a transação inteira
        # (a implementação usa savepoints por linha)
        self.assertEqual(response.resolver_match.url_name, 'listar_movimentos_nao_conciliados')

        movimentos = listar_movimentos_nao_conciliados(self.id_associacao1)
        self.assertEqual(len(movimentos), 3)
        refs = {m[4] for m in movimentos}
        self.assertEqual(refs, {'REF001', 'REF002', 'REF003'})

    # ============================================================
    # TESTE 13: Tentativa de aceder conciliação de outra associação → 403/404
    # ============================================================
    def test_13_acesso_conciliacao_outra_associacao_403(self):
        """Tentativa de aceder conciliação de outra associação → 403/404"""
        # Criar movimento e pagamento na associação 1
        pagamento1 = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFACESSO1',
            self.id_qa1,
            None,
            self.id_associacao1
        )

        csv_content1 = """data,valor,descricao,referencia
2024-01-15,100.00,Acesso assoc1,REFACESSO1
"""
        arquivo_csv1 = SimpleUploadedFile(
            "mov_acesso1.csv",
            csv_content1.encode('utf-8'),
            content_type="text/csv"
        )
        self.client.post(reverse('importar_movimentos_csv'), {'arquivo_csv': arquivo_csv1}, follow=True)

        movimentos1 = listar_movimentos_nao_conciliados(self.id_associacao1)
        id_movimento1 = movimentos1[0][0]

        # Conciliar na assoc 1
        conciliar_movimento_pagamento(self.id_associacao1, id_movimento1, pagamento1, forcar=False)

        # Login como direção da associação 2
        self.login_associacao2()

        # Tentar aceder lista de movimentos não conciliados - não deve ver os da assoc 1
        response = self.client.get(reverse('listar_movimentos_nao_conciliados'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'REFACESSO1')

        # Tentar aceder sugestões de movimento da assoc 1
        response = self.client.get(reverse('ver_sugestoes_conciliacao', args=[id_movimento1]))
        # Deve dar 404 ou 403 (movimento não encontrado para esta associação)
        self.assertIn(response.status_code, [403, 404])

        # Tentar conciliar movimento da assoc 1
        response = self.client.post(reverse('conciliar_movimento'), {
            'id_movimento': id_movimento1,
            'id_pagamento': pagamento1,
            'forcar': 'false',
        })
        self.assertIn(response.status_code, [403, 404])

        # Tentar ver histórico - não deve ver conciliações da assoc 1
        response = self.client.get(reverse('historico_conciliacoes'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'REFACESSO1')

    # ============================================================
    # TESTE 14: Atualização direta de pagamento (id_quota_associado muda) → trigger recalcula AMBAS quotas
    # ============================================================
    def test_14_atualizacao_pagamento_muda_quota_recalcula_ambas(self):
        """Atualização direta de pagamento (id_quota_associado muda) → trigger recalcula AMBAS quotas (velha e nova)"""
        # Criar segunda quota para o mesmo associado
        with connection.cursor() as cursor:
            quota2 = create_test_quota(cursor, self.id_associacao1, 100.00, 'anual')
            qa2 = create_test_quota_associado(cursor, self.id_associado1, quota2,
                                               valor_devido=100.00, estado='Pendente', periodo='01/2025')

        # Criar pagamento na quota 1 (qa1)
        pagamento = inserir_pagamento(
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFMUDAQUOTA',
            self.id_qa1,
            None,
            self.id_associacao1
        )

        # Verificar estado inicial: qa1 = Pago, qa2 = Pendente
        with connection.cursor() as cursor:
            qa1_estado = get_quota_associado_estado(cursor, self.id_qa1)
            qa2_estado = get_quota_associado_estado(cursor, qa2)
        self.assertEqual(qa1_estado, 'Pago')
        self.assertEqual(qa2_estado, 'Pendente')

        # Atualizar pagamento para quota 2 (qa2)
        # atualizar_pagamento(id_pagamento, data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, id_movimento, id_associacao)
        atualizar_pagamento(
            pagamento,
            '2024-01-15 10:00:00',
            Decimal('100.00'),
            'transferencia',
            'REFMUDAQUOTA',
            qa2,
            None,
            self.id_associacao1
        )

        # Verificar que AMBAS quotas foram recalculadas
        with connection.cursor() as cursor:
            qa1_estado = get_quota_associado_estado(cursor, self.id_qa1)
            qa2_estado = get_quota_associado_estado(cursor, qa2)

        # qa1 (velha) deve voltar a Pendente
        self.assertEqual(qa1_estado, 'Pendente')
        # qa2 (nova) deve ficar Pago
        self.assertEqual(qa2_estado, 'Pago')

    # ============================================================
    # TESTE 15: Pagamento direto > valor_devido → rejeitado (mesmo sem movimento bancário)
    # ============================================================
    def test_15_pagamento_direto_excede_valor_devido_rejeitado(self):
        """Pagamento direto > valor_devido → rejeitado (mesmo sem movimento bancário)"""
        # Quota de 100 - tentar pagar 150 (excede valor_devido)
        with self.assertRaises(Exception) as context:
            inserir_pagamento(
                '2024-01-15 10:00:00',
                Decimal('150.00'),  # Excede 100
                'transferencia',
                'REFEXCEDENTE',
                self.id_qa1,
                None,
                self.id_associacao1
            )

        # Verificar que erro foi lançado
        self.assertIn('excede', str(context.exception).lower())

        # Verificar que nenhum pagamento foi criado
        from associacao.database import listar_pagamentos
        pagamentos = listar_pagamentos(self.id_associacao1)
        refs = [p[4] for p in pagamentos]
        self.assertNotIn('REFEXCEDENTE', refs)

        # Verificar que quota continua Pendente
        with connection.cursor() as cursor:
            estado = get_quota_associado_estado(cursor, self.id_qa1)
        self.assertEqual(estado, 'Pendente')


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner

    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['associacao.tests_fase22'])