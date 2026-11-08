"""
Testes para o Sistema de Gestão de Associações
Bases de Dados II - Ficha 3
"""

from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.db import connection
from django.db import transaction
from unittest.mock import patch, MagicMock
from datetime import datetime

from . import database
from .auth_backends import DirecaoBackend, AssociadoBackend
from .decorators import direcao_required, associado_required


def create_test_associacao(cursor, nipc='123456789', nome='Associação Teste', email='direcao@teste.pt', password='direcao123'):
    """Cria uma associação de teste e retorna o ID gerado."""
    cursor.execute("""
        INSERT INTO associacao (nipc, nome, password_hash, email)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (nipc) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id_associacao
    """, [nipc, nome, make_password(password), email])
    return cursor.fetchone()[0]


def create_test_associado(cursor, id_associacao, numero=1, nome='Associado Teste', email='associado@teste.pt', password='associado123', nif='987654321'):
    """Cria um associado de teste e retorna o ID gerado."""
    cursor.execute("""
        INSERT INTO associado (numero_associado, nome, nif, email, data_adesao, estado, password_hash, id_associacao)
        VALUES (%s, %s, %s, %s, '2024-01-01', 'Ativo', %s, %s)
        ON CONFLICT (id_associacao, numero_associado) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id_associado
    """, [numero, nome, nif, email, make_password(password), id_associacao])
    return cursor.fetchone()[0]


def create_test_mandato(cursor, id_associacao, data_inicio='2024-01-01', data_fim=None):
    """Cria um mandato de teste e retorna o ID gerado."""
    cursor.execute("""
        INSERT INTO mandato (data_inicio, data_fim, id_associacao)
        VALUES (%s, %s, %s)
        RETURNING id_mandato
    """, [data_inicio, data_fim, id_associacao])
    return cursor.fetchone()[0]


def create_test_tipo_documento(cursor, id_associacao, nome='Acta'):
    """Cria um tipo de documento de teste e retorna o ID gerado."""
    cursor.execute("""
        INSERT INTO tipo_documento (nome_tipo_documento, descricao_tipo_documento, id_associacao)
        VALUES (%s, %s, %s)
        RETURNING id_tipo_documento
    """, [nome, f'Descrição de {nome}', id_associacao])
    return cursor.fetchone()[0]


def create_test_documento(cursor, id_associacao, id_tipo_documento, id_mandato, nome='Documento Teste'):
    """Cria um documento de teste e retorna o ID gerado."""
    cursor.execute("""
        INSERT INTO documento (nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato)
        VALUES (%s, NOW(), %s, 'documentos/teste.pdf', 'Observações', %s, %s, %s)
        RETURNING id_documento
    """, [nome, '2024-01-15', id_tipo_documento, id_associacao, id_mandato])
    return cursor.fetchone()[0]


class AuditAndStatisticsPhase24Tests(TestCase):
    """Cobertura da consulta MongoDB e métricas SQL da Fase 2.4."""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor, nipc='234567891')
            create_test_associado(
                cursor, self.id_associacao, numero=234, nif='123456782',
                email='fase24@teste.pt', password='fase24123',
            )

    def login_direcao(self):
        self.client.post(reverse('login'), {
            'login_type': 'associacao', 'nipc': '234567891', 'password': 'direcao123',
        })

    @patch('associacao.views.mongodb.get_audit_logs')
    def test_auditoria_aplica_filtros_e_isolamento(self, get_audit_logs):
        self.login_direcao()
        get_audit_logs.return_value = [{
            'timestamp': datetime(2026, 1, 2, 10, 30), 'action': 'update',
            'entity_type': 'associado', 'entity_id': 12, 'user_id': self.id_associacao,
            'user_type': 'direcao', 'details': {},
        }]

        response = self.client.get(reverse('auditoria'), {
            'data_inicio': '2026-01-01', 'data_fim': '2026-01-31',
            'operacao': 'update', 'entidade': 'associado',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'associado')
        get_audit_logs.assert_called_once()
        self.assertEqual(get_audit_logs.call_args.kwargs['association_id'], self.id_associacao)
        self.assertEqual(get_audit_logs.call_args.kwargs['action'], 'update')
        self.assertEqual(get_audit_logs.call_args.kwargs['entity_type'], 'associado')

    def test_auditoria_bloqueia_associado(self):
        self.client.post(reverse('login'), {
            'login_type': 'associado', 'nipc': '123456782', 'password': 'fase24123',
        })
        response = self.client.get(reverse('auditoria'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard_associado'), response.url)

    def test_estatisticas_usa_dados_da_associacao(self):
        self.login_direcao()
        response = self.client.get(reverse('estatisticas'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_associados'], 1)
        self.assertEqual(response.context['associados_ativos'], 1)
        self.assertEqual(response.context['associados_inativos'], 0)


class MandatosPassagemPossePhase25Tests(TransactionTestCase):
    """Regras transacionais da composição dos mandatos e passagem de posse."""

    sequence = 0

    def setUp(self):
        type(self).sequence += 1
        self.nipc = str(345678900 + self.sequence)
        self.numero_base = 3450 + self.sequence * 10
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor, nipc=self.nipc, password='direcao-antiga')
            self.id_presidente = create_test_associado(
                cursor, self.id_associacao, numero=self.numero_base, nif=str(345678900 + self.sequence), nome='Nova Presidente',
            )
            self.id_tesoureiro = create_test_associado(
                cursor, self.id_associacao, numero=self.numero_base + 1, nif=str(456789100 + self.sequence), nome='Novo Tesoureiro',
            )
            cursor.execute("INSERT INTO mandato (data_inicio, id_associacao) VALUES ('2024-01-01', %s) RETURNING id_mandato", [self.id_associacao])
            self.id_mandato = cursor.fetchone()[0]
            cursor.execute("INSERT INTO orgao_social (nome, id_associacao) VALUES ('Direção', %s) RETURNING id_orgao_social", [self.id_associacao])
            id_orgao = cursor.fetchone()[0]
            cursor.execute("INSERT INTO cargo (nome, id_orgao_social) VALUES ('Presidente', %s) RETURNING id_cargo", [id_orgao])
            self.id_cargo_presidente = cursor.fetchone()[0]
            cursor.execute("INSERT INTO cargo (nome, id_orgao_social) VALUES ('Tesoureiro', %s) RETURNING id_cargo", [id_orgao])
            self.id_cargo_tesoureiro = cursor.fetchone()[0]

    def test_impede_sobreposicao_de_mandatos(self):
        self.assertTrue(database.mandato_sobrepoe('2024-06-01', '2025-01-01', self.id_associacao))

    def test_impede_cargo_duplicado_no_mesmo_mandato(self):
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO exercicio_cargo (data_inicio, id_associado, id_cargo, id_mandato) VALUES ('2024-01-01', %s, %s, %s)", [self.id_presidente, self.id_cargo_presidente, self.id_mandato])
        with self.assertRaises(Exception):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("INSERT INTO exercicio_cargo (data_inicio, id_associado, id_cargo, id_mandato) VALUES ('2024-01-01', %s, %s, %s)", [self.id_tesoureiro, self.id_cargo_presidente, self.id_mandato])

    def test_passagem_posse_roda_credenciais_e_cria_composicao(self):
        from django.contrib.auth.hashers import check_password, make_password
        database.passagem_posse(
            self.id_mandato, '2026-01-01', None, self.id_presidente,
            [
                {'id_associado': self.id_presidente, 'id_cargo': self.id_cargo_presidente},
                {'id_associado': self.id_tesoureiro, 'id_cargo': self.id_cargo_tesoureiro},
            ], make_password('nova-palavra-passe-segura'), self.id_associacao,
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT data_fim FROM mandato WHERE id_mandato = %s', [self.id_mandato])
            self.assertEqual(str(cursor.fetchone()[0]), '2025-12-31')
            cursor.execute("""
                SELECT COUNT(*) FROM exercicio_cargo ec
                JOIN mandato m ON m.id_mandato = ec.id_mandato
                WHERE ec.id_mandato <> %s AND m.id_associacao = %s
            """, [self.id_mandato, self.id_associacao])
            self.assertEqual(cursor.fetchone()[0], 2)
            cursor.execute('SELECT password_hash FROM associacao WHERE id_associacao = %s', [self.id_associacao])
            self.assertTrue(check_password('nova-palavra-passe-segura', cursor.fetchone()[0]))
        self.assertIsNotNone(DirecaoBackend().authenticate(None, username=self.nipc, password='nova-palavra-passe-segura'))

    def test_falha_da_passagem_reverte_todas_as_alteracoes(self):
        from django.contrib.auth.hashers import make_password
        with self.assertRaises(Exception):
            with transaction.atomic():
                database.passagem_posse(
                    self.id_mandato, '2026-01-01', None, self.id_presidente,
                    [{'id_associado': self.id_tesoureiro, 'id_cargo': self.id_cargo_tesoureiro}],
                    make_password('nao-deve-ser-gravada'), self.id_associacao,
                )
        with connection.cursor() as cursor:
            cursor.execute('SELECT data_fim FROM mandato WHERE id_mandato = %s', [self.id_mandato])
            self.assertIsNone(cursor.fetchone()[0])
            cursor.execute('SELECT COUNT(*) FROM mandato WHERE id_associacao = %s', [self.id_associacao])
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_rotacao_invalida_sessao_administrativa_anterior(self):
        client = Client()
        self.assertTrue(client.login(username=self.nipc, password='direcao-antiga'))
        with connection.cursor() as cursor:
            cursor.execute('UPDATE associacao SET password_hash = %s WHERE id_associacao = %s', [
                make_password('credencial-substituida'), self.id_associacao,
            ])
        response = client.get(reverse('dashboard_direcao'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


# ==========================================
# TESTES DE AUTENTICAÇÃO
# ==========================================

class AuthenticationTests(TestCase):
    """Testes para autenticação dual (Direção e Associado)"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            create_test_associado(cursor, self.id_associacao)

    def test_login_direcao_success(self):
        """Testa login bem-sucedido da Direção"""
        response = self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/dashboard/direcao/'))

    def test_login_associado_success(self):
        """Testa login bem-sucedido de Associado"""
        response = self.client.post(reverse('login'), {
            'nipc': '987654321',
            'password': 'associado123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/dashboard/associado/'))

    def test_login_associado_ignora_password_vazia_do_outro_painel(self):
        """O painel da associação também envia password; a vazia não pode apagar a do associado."""
        response = self.client.post(reverse('login'), {
            'login_type': 'associado',
            'associacao_nipc': '123456789',
            'nif': '987654321',
            'nipc': '',
            'password': ['associado123', ''],
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/dashboard/associado/'))

    def test_login_associado_com_campo_de_password_proprio(self):
        response = self.client.post(reverse('login'), {
            'login_type': 'associado',
            'associacao_nipc': '123456789',
            'nif': '987654321',
            'password_associado': 'associado123',
            'password_associacao': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/dashboard/associado/'))

    def test_login_associacao_ignora_password_vazia_do_painel_associado(self):
        response = self.client.post(reverse('login'), {
            'login_type': 'associacao',
            'nif': '',
            'nipc': '123456789',
            'password': ['', 'direcao123'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/dashboard/direcao/'))

    def test_login_invalid_credentials(self):
        """Testa login com credenciais inválidas"""
        response = self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'senha_errada'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Credenciais inválidas')

    def test_login_empty_fields(self):
        """Testa login com campos vazios"""
        response = self.client.post(reverse('login'), {
            'nipc': '',
            'password': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Por favor, preencha NIF e palavra-passe')

    def test_login_get_renders_without_posted_values(self):
        """GET /login/ não tem POST; a página não pode falhar a procurar chaves em falta."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_nipc_associado"')
        self.assertContains(response, 'value=""')

    def test_logout(self):
        """Testa logout"""
        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))

    def test_direcao_backend_authenticate(self):
        """Testa DirecaoBackend directamente"""
        backend = DirecaoBackend()
        user = backend.authenticate(None, username='123456789', password='direcao123')
        self.assertIsNotNone(user)
        self.assertEqual(user.tipo, 'direcao')

    def test_associado_backend_authenticate(self):
        """Testa AssociadoBackend directamente"""
        backend = AssociadoBackend()
        user = backend.authenticate(None, username='987654321', password='associado123')
        self.assertIsNotNone(user)
        self.assertEqual(user.tipo, 'associado')

    def test_login_associado_com_nif_repetido_exige_nipc_da_associacao(self):
        with connection.cursor() as cursor:
            id_associacao_2 = create_test_associacao(
                cursor, nipc='234567891', nome='Associação Dois', password='direcao-dois'
            )
            create_test_associado(
                cursor, id_associacao_2, numero=1, nif='987654321', password='senha-dois'
            )

        backend = AssociadoBackend()
        self.assertIsNone(backend.authenticate(None, username='987654321', password='associado123'))
        user = backend.authenticate(
            None, username='987654321', password='senha-dois', association_nipc='234567891'
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.id_associacao, id_associacao_2)

    def test_backend_rejects_wrong_password(self):
        """Testa que backends rejeitam senha errada"""
        backend = DirecaoBackend()
        user = backend.authenticate(None, username='123456789', password='errada')
        self.assertIsNone(user)


# ==========================================
# TESTES DE PERMISSÕES (DECORATORS)
# ==========================================

class PermissionTests(TestCase):
    """Testes para decorators de permissão"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            create_test_associado(cursor, self.id_associacao, numero=999, nome='Teste Bloqueio', email='bloqueio@teste.pt', password='teste123')

    def test_direcao_required_redirects_anonymous(self):
        """Testa que direcao_required redireciona utilizador anónimo"""
        response = self.client.get(reverse('dashboard_direcao'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_associado_required_redirects_anonymous(self):
        """Testa que associado_required redireciona utilizador anónimo"""
        response = self.client.get(reverse('dashboard_associado'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_direcao_required_blocks_associado(self):
        """Testa que direcao_required bloqueia associado"""
        self.client.post(reverse('login'), {
            'nipc': '987654321',
            'password': 'teste123'
        })
        response = self.client.get(reverse('dashboard_direcao'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/associado/', response.url)

    def test_associado_required_blocks_direcao(self):
        """Testa que associado_required bloqueia direção"""
        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })
        response = self.client.get(reverse('dashboard_associado'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/direcao/', response.url)


# ==========================================
# TESTES DE GESTÃO DOCUMENTAL (FASE 2.3)
# ==========================================

class DocumentoTests(TestCase):
    """Testes para gestão documental"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            self.id_associado = create_test_associado(cursor, self.id_associacao)
            self.id_mandato = create_test_mandato(cursor, self.id_associacao)
            self.id_tipo_documento = create_test_tipo_documento(cursor, self.id_associacao)

        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })

    def test_listar_tipos_documento(self):
        """Testa listagem de tipos de documento"""
        response = self.client.get(reverse('listar_tipos_documento'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tipos de Documento')

    def test_registar_tipo_documento(self):
        """Testa registo de tipo de documento"""
        response = self.client.post(reverse('registar_tipo_documento'), {
            'nome_tipo_documento': 'Relatório',
            'descricao_tipo_documento': 'Relatórios anuais',
            'id_associacao': self.id_associacao,
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_registar_tipo_documento_invalid(self):
        """Testa registo de tipo de documento com dados inválidos"""
        response = self.client.post(reverse('registar_tipo_documento'), {
            'nome_tipo_documento': '',
            'descricao_tipo_documento': 'Actas de reuniões',
            'id_associacao': self.id_associacao,
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('nome_tipo_documento', form.errors)

    def test_editar_tipo_documento(self):
        """Testa edição de tipo de documento"""
        response = self.client.post(reverse('editar_tipo_documento', args=[self.id_tipo_documento]), {
            'nome_tipo_documento': 'Acta Actualizada',
            'descricao_tipo_documento': 'Actas de reuniões actualizadas',
            'id_associacao': self.id_associacao,
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_eliminar_tipo_documento(self):
        """Testa eliminação de tipo de documento"""
        # Criar novo tipo para eliminar
        with connection.cursor() as cursor:
            id_tipo = create_test_tipo_documento(cursor, self.id_associacao, 'ParaEliminar')

        response = self.client.post(reverse('eliminar_tipo_documento', args=[id_tipo]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_listar_documentos(self):
        """Testa listagem de documentos"""
        response = self.client.get(reverse('listar_documentos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documentos')

    def test_registar_documento(self):
        """Testa registo de documento com ficheiro"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        response = self.client.post(reverse('registar_documento'), {
            'nome_documento': 'Documento Teste',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações de teste',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_registar_documento_invalid_extension(self):
        """Testa registo de documento com extensão inválida"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.exe",
            b"executable content",
            content_type="application/x-executable"
        )

        response = self.client.post(reverse('registar_documento'), {
            'nome_documento': 'Documento Teste',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações de teste',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('ficheiro', form.errors)

    def test_registar_documento_too_large(self):
        """Testa registo de documento demasiado grande"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Criar ficheiro de 11MB (limite é 10MB)
        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"x" * (11 * 1024 * 1024),
            content_type="application/pdf"
        )

        response = self.client.post(reverse('registar_documento'), {
            'nome_documento': 'Documento Teste',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações de teste',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('ficheiro', form.errors)

    def test_editar_documento(self):
        """Testa edição de documento"""
        # Criar documento primeiro
        from django.core.files.uploadedfile import SimpleUploadedFile
        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        with connection.cursor() as cursor:
            id_documento = create_test_documento(cursor, self.id_associacao, self.id_tipo_documento, self.id_mandato)

        # Editar documento
        response = self.client.post(reverse('editar_documento', args=[id_documento]), {
            'nome_documento': 'Documento Editado',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações editadas',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_editar_documento_com_novo_ficheiro(self):
        """Testa edição de documento com substituição de ficheiro"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro1 = SimpleUploadedFile(
            "teste1.pdf",
            b"%PDF-1.4\nteste content 1",
            content_type="application/pdf"
        )

        ficheiro2 = SimpleUploadedFile(
            "teste2.pdf",
            b"%PDF-1.4\nteste content 2",
            content_type="application/pdf"
        )

        with connection.cursor() as cursor:
            id_documento = create_test_documento(cursor, self.id_associacao, self.id_tipo_documento, self.id_mandato)

        # Editar documento com novo ficheiro
        response = self.client.post(reverse('editar_documento', args=[id_documento]), {
            'nome_documento': 'Documento Editado',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações editadas',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro2,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_eliminar_documento(self):
        """Testa eliminação de documento"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        with connection.cursor() as cursor:
            id_documento = create_test_documento(cursor, self.id_associacao, self.id_tipo_documento, self.id_mandato)

        response = self.client.post(reverse('eliminar_documento', args=[id_documento]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_descarregar_documento(self):
        """Testa download de documento"""
        import os
        from django.conf import settings

        # Criar ficheiro físico primeiro
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'documentos', str(self.id_associacao))
        os.makedirs(upload_dir, exist_ok=True)
        ficheiro_path = os.path.join(upload_dir, 'teste_download.pdf')
        with open(ficheiro_path, 'wb') as f:
            f.write(b"%PDF-1.4\nteste content")

        with connection.cursor() as cursor:
            # Criar documento com o caminho do ficheiro real
            cursor.execute("""
                INSERT INTO documento (nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato)
                VALUES (%s, NOW(), %s, %s, 'Observações', %s, %s, %s)
                RETURNING id_documento
            """, ['Documento Download', '2024-01-15', 'documentos/' + str(self.id_associacao) + '/teste_download.pdf',
                  self.id_tipo_documento, self.id_associacao, self.id_mandato])
            id_documento = cursor.fetchone()[0]

        response = self.client.get(reverse('descarregar_documento', args=[id_documento]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_isolamento_tipos_documento(self):
        """Testa isolamento multi-tenancy em tipos de documento"""
        # Criar outra associação
        with connection.cursor() as cursor:
            id_associacao2 = create_test_associacao(cursor, nipc='999999999', nome='Outra Associação')
            create_test_tipo_documento(cursor, id_associacao2, 'Tipo Outra')

        # Tentar aceder tipo da outra associação
        response = self.client.get(reverse('editar_tipo_documento', args=[999999]))  # ID inexistente
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_isolamento_documentos(self):
        """Testa isolamento multi-tenancy em documentos"""
        # Criar outra associação
        with connection.cursor() as cursor:
            id_associacao2 = create_test_associacao(cursor, nipc='999999999', nome='Outra Associação')
            id_tipo2 = create_test_tipo_documento(cursor, id_associacao2, 'Tipo Outra')
            id_mandato2 = create_test_mandato(cursor, id_associacao2)
            id_documento2 = create_test_documento(cursor, id_associacao2, id_tipo2, id_mandato2)

        # Tentar aceder documento da outra associação
        response = self.client.get(reverse('editar_documento', args=[id_documento2]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_associado_nao_acede_documentos(self):
        """Testa que associado não acede à gestão de documentos"""
        self.client.logout()
        self.client.post(reverse('login'), {
            'nipc': '987654321',
            'password': 'associado123'
        })

        response = self.client.get(reverse('listar_documentos'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/associado/', response.url)

        response = self.client.get(reverse('listar_tipos_documento'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/associado/', response.url)

    def test_tipo_documento_form_valid(self):
        """Testa TipoDocumentoForm válido"""
        from associacao.forms import TipoDocumentoForm
        form = TipoDocumentoForm(data={
            'nome_tipo_documento': 'Teste',
            'descricao_tipo_documento': 'Descrição',
            'id_associacao': self.id_associacao,
        })
        self.assertTrue(form.is_valid())

    def test_tipo_documento_form_invalid(self):
        """Testa TipoDocumentoForm inválido"""
        from associacao.forms import TipoDocumentoForm
        form = TipoDocumentoForm(data={
            'nome_tipo_documento': '',
            'descricao_tipo_documento': 'Descrição',
            'id_associacao': self.id_associacao,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('nome_tipo_documento', form.errors)

    def test_documento_form_valid(self):
        """Testa DocumentoForm válido"""
        from associacao.forms import DocumentoForm
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        form = DocumentoForm(
            data={
                'nome_documento': 'Teste',
                'data_upload_0': '2024-01-15',
                'data_upload_1': '10:00',
                'data_documento': '2024-01-15',
                'observacoes': 'Obs',
                'id_tipo_documento': str(self.id_tipo_documento),
                'id_mandato': str(self.id_mandato),
                'id_associacao': self.id_associacao,
            },
            files={'ficheiro': ficheiro},
            id_associacao=self.id_associacao
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_documento_form_invalid_extension(self):
        """Testa DocumentoForm com extensão inválida"""
        from associacao.forms import DocumentoForm
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.exe",
            b"exe content",
            content_type="application/x-executable"
        )

        form = DocumentoForm(
            data={
                'nome_documento': 'Teste',
                'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
                'data_documento': '2024-01-15',
                'observacoes': 'Obs',
                'id_tipo_documento': str(self.id_tipo_documento),
                'id_mandato': str(self.id_mandato),
                'id_associacao': self.id_associacao,
            },
            files={'ficheiro': ficheiro},
            id_associacao=self.id_associacao
        )
        self.assertFalse(form.is_valid())
        self.assertIn('ficheiro', form.errors)


class PrimeiroAcessoAssociadoTests(TestCase):
    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            self.id_associado = create_test_associado(cursor, self.id_associacao)
            cursor.execute(
                'UPDATE associado SET exigir_alteracao_password = TRUE WHERE id_associado = %s',
                [self.id_associado],
            )

    def test_primeiro_login_exige_nova_palavra_passe(self):
        response = self.client.post(reverse('login'), {
            'login_type': 'associado', 'nipc': '987654321', 'password': 'associado123',
        })
        self.assertRedirects(response, reverse('definir_palavra_passe_associado'))

        response = self.client.post(reverse('definir_palavra_passe_associado'), {
            'nova_palavra_passe': 'nova-palavra-passe-segura',
            'confirmacao': 'nova-palavra-passe-segura',
        })
        self.assertRedirects(response, reverse('dashboard_associado'))
        with connection.cursor() as cursor:
            cursor.execute('SELECT exigir_alteracao_password FROM associado WHERE id_associado = %s', [self.id_associado])
            self.assertFalse(cursor.fetchone()[0])


class HardcodedPresentationRegressionTests(TestCase):
    """Garante que as listagens vazias não mostram valores demonstrativos."""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            create_test_associacao(cursor)
        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123',
        })

    def test_listagens_vazias_usam_valores_reais(self):
        for url_name in ('listar_associados', 'listar_quotas', 'listar_quotas_associado', 'listar_pagamentos', 'listar_mandatos'):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'Ana Martins')
            self.assertNotContains(response, '2 880,00')
            self.assertNotContains(response, '128')

        response = self.client.get(reverse('listar_associados'))
        self.assertContains(response, '0 ativos · 0 inativos')


# ==========================================
# TESTES DE CRUD - ASSOCIADO
# ==========================================

class AssociadoCRUDTests(TestCase):
    """Testes CRUD para Associados"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)

        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })

    def test_listar_associados(self):
        """Testa listagem de associados"""
        response = self.client.get(reverse('listar_associados'))
        self.assertEqual(response.status_code, 200)

    def test_registar_associado(self):
        """Testa registo de associado"""
        response = self.client.post(reverse('registar_associado'), {
            'numero_associado': 100,
            'nome': 'Novo Associado',
            'nif': '111222333',
            'email': 'novo@teste.pt',
            'data_adesao': '2024-01-15',
            'estado': 'Ativo',
            'id_associacao': self.id_associacao
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Credenciais criadas')

    def test_registar_associado_invalid_data(self):
        """Testa registo com dados inválidos"""
        response = self.client.post(reverse('registar_associado'), {
            'numero_associado': -1,
            'nome': '',
        })
        # Should show form with errors
        self.assertIn(response.status_code, [200, 302])

    def test_registar_associado_numero_duplicado_mostra_erro_no_formulario(self):
        with connection.cursor() as cursor:
            create_test_associado(cursor, self.id_associacao, numero=1)

        response = self.client.post(reverse('registar_associado'), {
            'numero_associado': 1,
            'nome': 'Associado Duplicado',
            'nif': '111222333',
            'data_adesao': '2024-01-15',
            'estado': 'Ativo',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este número de associado já se encontra registado.')

    def test_registar_associado_permite_numero_existente_noutra_associacao(self):
        with connection.cursor() as cursor:
            id_associacao_2 = create_test_associacao(
                cursor, nipc='234567891', nome='Associação Dois', password='direcao-dois'
            )
            create_test_associado(cursor, id_associacao_2, numero=1, nif='222333444')

        response = self.client.post(reverse('registar_associado'), {
            'numero_associado': 1,
            'nome': 'Associado Número Um',
            'nif': '111222333',
            'data_adesao': '2024-01-15',
            'estado': 'Ativo',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Credenciais criadas')
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM associado WHERE id_associacao = %s AND numero_associado = 1',
                [self.id_associacao],
            )
            self.assertEqual(cursor.fetchone()[0], 1)


# ==========================================
# TESTES DE CRUD - QUOTA
# ==========================================

class QuotaCRUDTests(TestCase):
    """Testes CRUD para Quotas"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)

        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })

    def test_listar_quotas(self):
        """Testa listagem de quotas"""
        response = self.client.get(reverse('listar_quotas'))
        self.assertEqual(response.status_code, 200)

    def test_registar_quota(self):
        """Testa registo de quota"""
        response = self.client.post(reverse('registar_quota'), {
            'designacao_quota': 'Quota Mensal',
            'valor_quota': '25.00',
            'periodicidade_quota': 'Mensal',
            'data_inicio_quota': '2024-01-01',
            'id_associacao': self.id_associacao
        })
        self.assertEqual(response.status_code, 302)
        # Redirects to listar_quotas which is /quotas/
        self.assertIn('quotas', response.url)


# ==========================================
# TESTES DE CRUD - EVENTO
# ==========================================

class EventoCRUDTests(TestCase):
    """Testes CRUD para Eventos"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)

        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })

    def test_listar_eventos(self):
        """Testa listagem de eventos"""
        response = self.client.get(reverse('listar_eventos'))
        self.assertEqual(response.status_code, 200)

    def test_registar_evento(self):
        """Testa registo de evento"""
        response = self.client.post(reverse('registar_evento'), {
            'nome_evento': 'Evento Teste',
            'data_inicio_evento_0': '2024-12-01',
            'data_inicio_evento_1': '14:00',
            'estado_evento': 'Planeado',
            'id_associacao': self.id_associacao
        })
        self.assertEqual(response.status_code, 302)


# ==========================================
# TESTES DE ISOLAMENTO DE DADOS
# ==========================================

class DataIsolationTests(TestCase):
    """Testes de isolamento de dados entre associações"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao1 = create_test_associacao(cursor, nipc='123456789', email='direcao@teste.pt')
            create_test_associado(cursor, self.id_associacao1, numero=1, email='associado@teste.pt')

        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })

    def test_listar_associados_returns_list(self):
        """Testa que listar_associados retorna uma lista de associados"""
        response = self.client.get(reverse('listar_associados'))
        self.assertEqual(response.status_code, 200)
        # Verifica que o associado criado no setUp aparece na lista
        self.assertContains(response, 'Associado Teste')


# ==========================================
# TESTES DE MODELS/FUNÇÕES DE BASE DE DADOS
# ==========================================

class DatabaseFunctionTests(TestCase):
    """Testes para funções de base de dados"""

    def setUp(self):
        with connection.cursor() as cursor:
            create_test_associacao(cursor)

    def test_listar_associados(self):
        """Testa listar_associados"""
        associados = database.listar_associados()
        self.assertIsInstance(associados, list)

    def test_listar_quotas(self):
        """Testa listar_quotas"""
        quotas = database.listar_quotas()
        self.assertIsInstance(quotas, list)

    def test_listar_eventos(self):
        """Testa listar_eventos"""
        eventos = database.listar_eventos()
        self.assertIsInstance(eventos, list)

    def test_listar_localidades(self):
        """Testa listar_localidades"""
        localidades = database.listar_localidades()
        self.assertIsInstance(localidades, list)

    def test_listar_associacoes_para_selecao(self):
        """Testa listar_associacoes_para_selecao"""
        associacoes = database.listar_associacoes_para_selecao()
        self.assertIsInstance(associacoes, list)


# ==========================================
# TESTES DE FORMULÁRIOS
# ==========================================

class FormTests(TestCase):
    """Testes para formulários"""

    def test_associado_form_valid(self):
        """Testa AssociadoForm válido"""
        from .forms import AssociadoForm
        form = AssociadoForm(data={
            'numero_associado': 200,
            'nome': 'Teste Form',
            'nif': '123456789',
            'data_adesao': '2024-01-01',
            'estado': 'Ativo',
            'id_associacao': 1
        })
        self.assertTrue(form.is_valid())

    def test_associado_form_invalid_missing_nome(self):
        """Testa AssociadoForm inválido sem nome"""
        from .forms import AssociadoForm
        form = AssociadoForm(data={
            'numero_associado': 201,
            'data_adesao': '2024-01-01',
            'estado': 'Ativo',
            'id_associacao': 1
        })
        self.assertFalse(form.is_valid())
        self.assertIn('nome', form.errors)

    def test_quota_form_valid(self):
        """Testa QuotaForm válido"""
        from .forms import QuotaForm
        form = QuotaForm(data={
            'designacao_quota': 'Quota Anual',
            'valor_quota': '100.00',
            'periodicidade_quota': 'Anual',
            'data_inicio_quota': '2024-01-01',
            'id_associacao': 1
        })
        self.assertTrue(form.is_valid())

    def test_evento_form_invalid_dates(self):
        """Testa EventoForm com datas inválidas"""
        from .forms import EventoForm
        form = EventoForm(data={
            'nome_evento': 'Evento Teste',
            'data_inicio_evento_0': '2024-12-31',
            'data_inicio_evento_1': '14:00',
            'data_fim_evento_0': '2024-12-30',
            'data_fim_evento_1': '14:00',
            'estado_evento': 'Planeado',
            'id_associacao': 1
        })
        self.assertFalse(form.is_valid())
        self.assertIn('data_fim_evento', form.errors)


# ==========================================
# TESTES DE DASHBOARDS
# ==========================================

class DashboardTests(TestCase):
    """Testes para dashboards"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            create_test_associado(cursor, self.id_associacao)

    def test_dashboard_direcao_requires_login(self):
        """Testa que dashboard da direção requer login"""
        response = self.client.get(reverse('dashboard_direcao'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_associado_requires_login(self):
        """Testa que dashboard do associado requer login"""
        response = self.client.get(reverse('dashboard_associado'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_direcao_content(self):
        """Testa conteúdo do dashboard da direção"""
        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })
        response = self.client.get(reverse('dashboard_direcao'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visão geral')

    def test_dashboard_associado_content(self):
        """Testa conteúdo do dashboard do associado"""
        self.client.post(reverse('login'), {
            'nipc': '987654321',
            'password': 'associado123'
        })
        response = self.client.get(reverse('dashboard_associado'))
        self.assertEqual(response.status_code, 200)
        # The page title is "Início — Portal do Associado" and shows "Bem-vindo"
        self.assertContains(response, 'Bem-vindo')
        self.assertContains(response, 'Portal do Associado')


# ==========================================
# TESTES DE PORTAL DO ASSOCIADO
# ==========================================

class PortalTests(TestCase):
    """Testes para portal do associado"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            create_test_associado(cursor, self.id_associacao)

        self.client.post(reverse('login'), {
            'nipc': '987654321',
            'password': 'associado123'
        })

    def test_portal_eventos(self):
        """Testa portal de eventos"""
        response = self.client.get(reverse('portal_eventos'))
        self.assertEqual(response.status_code, 200)

    def test_portal_associacao(self):
        """Testa portal da associação"""
        response = self.client.get(reverse('portal_associacao'))
        self.assertEqual(response.status_code, 200)

    def test_portal_minhas_quotas(self):
        """Testa portal de quotas"""
        response = self.client.get(reverse('portal_minhas_quotas'))
        self.assertEqual(response.status_code, 200)

    def test_portal_perfil(self):
        """Testa portal de perfil"""
        response = self.client.get(reverse('portal_perfil'))
        self.assertEqual(response.status_code, 200)

    def test_seed_localidades_continente_e_endpoint_codigo_postal(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM localidade')
            total_localidades = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM localidade WHERE codigo_postal = '3750-011'")
            codigo_exemplo = cursor.fetchone()[0]

        self.assertGreaterEqual(total_localidades, 196900)
        self.assertGreater(codigo_exemplo, 0)
        resposta = self.client.get(reverse('localidade_por_codigo_postal'), {'codigo_postal': '3750-011'})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['success'])
        self.assertEqual(resposta.json()['id_localidade'] > 0, True)

    def test_perfil_atualiza_dados_e_password_em_todas_associacoes_do_mesmo_nif(self):
        """O perfil pessoal é partilhado; dados associativos continuam locais."""
        with connection.cursor() as cursor:
            id_associacao_2 = create_test_associacao(
                cursor, nipc='234567891', nome='Associação Dois', password='direcao-dois'
            )
            id_associado_2 = create_test_associado(
                cursor, id_associacao_2, numero=2, nif='987654321',
                nome='Nome Antigo', email='antigo@teste.pt', password='senha-antiga'
            )

        response = self.client.post(reverse('portal_perfil'), {
            'nome': 'Nome Atualizado', 'nif': '111222333', 'data_nascimento': '1990-01-02',
            'email': 'novo@teste.pt', 'telefone': '912345678', 'tipo_via': 'Rua',
            'nome_via': 'da Liberdade', 'numero_porta': '10', 'andar': '2.º',
            'codigo_postal': '1000-001', 'id_localidade': '', 'localidade': '',
            'palavra_passe_atual': 'associado123',
            'nova_palavra_passe': 'nova-palavra-passe-segura',
            'confirmacao_palavra_passe': 'nova-palavra-passe-segura',
        })
        self.assertRedirects(response, reverse('portal_perfil'))

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT nome, nif, email, telefone FROM associado WHERE id_associado = %s',
                [id_associado_2],
            )
            self.assertEqual(cursor.fetchone(), ('Nome Atualizado', '111222333', 'novo@teste.pt', '912345678'))

        self.assertIsNotNone(AssociadoBackend().authenticate(
            None, username='111222333', password='nova-palavra-passe-segura',
            association_nipc='234567891'
        ))

    def test_direcao_nao_acessa_portal(self):
        """Testa que direção não acede ao portal do associado"""
        self.client.logout()
        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })
        response = self.client.get(reverse('portal_eventos'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/direcao/', response.url)


# ==========================================
# TESTES DE GESTÃO DOCUMENTAL (FASE 2.3)
# ==========================================

class DocumentoTests(TestCase):
    """Testes para gestão documental"""

    def setUp(self):
        self.client = Client()
        with connection.cursor() as cursor:
            self.id_associacao = create_test_associacao(cursor)
            self.id_associado = create_test_associado(cursor, self.id_associacao)
            self.id_mandato = create_test_mandato(cursor, self.id_associacao)
            self.id_tipo_documento = create_test_tipo_documento(cursor, self.id_associacao)

        self.client.post(reverse('login'), {
            'nipc': '123456789',
            'password': 'direcao123'
        })

    def test_listar_tipos_documento(self):
        """Testa listagem de tipos de documento"""
        response = self.client.get(reverse('listar_tipos_documento'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tipos de Documento')

    def test_registar_tipo_documento(self):
        """Testa registo de tipo de documento"""
        response = self.client.post(reverse('registar_tipo_documento'), {
            'nome_tipo_documento': 'Relatório',
            'descricao_tipo_documento': 'Relatórios anuais',
            'id_associacao': self.id_associacao,
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_registar_tipo_documento_invalid(self):
        """Testa registo de tipo de documento com dados inválidos"""
        response = self.client.post(reverse('registar_tipo_documento'), {
            'nome_tipo_documento': '',
            'descricao_tipo_documento': 'Actas de reuniões',
            'id_associacao': self.id_associacao,
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('nome_tipo_documento', form.errors)

    def test_editar_tipo_documento(self):
        """Testa edição de tipo de documento"""
        response = self.client.post(reverse('editar_tipo_documento', args=[self.id_tipo_documento]), {
            'nome_tipo_documento': 'Acta Actualizada',
            'descricao_tipo_documento': 'Actas de reuniões actualizadas',
            'id_associacao': self.id_associacao,
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_eliminar_tipo_documento(self):
        """Testa eliminação de tipo de documento"""
        # Criar novo tipo para eliminar
        with connection.cursor() as cursor:
            id_tipo = create_test_tipo_documento(cursor, self.id_associacao, 'ParaEliminar')

        response = self.client.post(reverse('eliminar_tipo_documento', args=[id_tipo]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_listar_documentos(self):
        """Testa listagem de documentos"""
        response = self.client.get(reverse('listar_documentos'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documentos')

    def test_registar_documento(self):
        """Testa registo de documento com ficheiro"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        response = self.client.post(reverse('registar_documento'), {
            'nome_documento': 'Documento Teste',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações de teste',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_registar_documento_invalid_extension(self):
        """Testa registo de documento com extensão inválida"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.exe",
            b"executable content",
            content_type="application/x-executable"
        )

        response = self.client.post(reverse('registar_documento'), {
            'nome_documento': 'Documento Teste',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações de teste',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('ficheiro', form.errors)

    def test_registar_documento_too_large(self):
        """Testa registo de documento demasiado grande"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Criar ficheiro de 11MB (limite é 10MB)
        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"x" * (11 * 1024 * 1024),
            content_type="application/pdf"
        )

        response = self.client.post(reverse('registar_documento'), {
            'nome_documento': 'Documento Teste',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações de teste',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('ficheiro', form.errors)

    def test_editar_documento(self):
        """Testa edição de documento"""
        # Criar documento primeiro
        from django.core.files.uploadedfile import SimpleUploadedFile
        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        with connection.cursor() as cursor:
            id_documento = create_test_documento(cursor, self.id_associacao, self.id_tipo_documento, self.id_mandato)

        # Editar documento
        response = self.client.post(reverse('editar_documento', args=[id_documento]), {
            'nome_documento': 'Documento Editado',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações editadas',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_editar_documento_com_novo_ficheiro(self):
        """Testa edição de documento com substituição de ficheiro"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro1 = SimpleUploadedFile(
            "teste1.pdf",
            b"%PDF-1.4\nteste content 1",
            content_type="application/pdf"
        )

        ficheiro2 = SimpleUploadedFile(
            "teste2.pdf",
            b"%PDF-1.4\nteste content 2",
            content_type="application/pdf"
        )

        with connection.cursor() as cursor:
            id_documento = create_test_documento(cursor, self.id_associacao, self.id_tipo_documento, self.id_mandato)

        # Editar documento com novo ficheiro
        response = self.client.post(reverse('editar_documento', args=[id_documento]), {
            'nome_documento': 'Documento Editado',
            'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
            'data_documento': '2024-01-15',
            'observacoes': 'Observações editadas',
            'id_tipo_documento': self.id_tipo_documento,
            'id_mandato': self.id_mandato,
            'id_associacao': self.id_associacao,
            'ficheiro': ficheiro2,
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_eliminar_documento(self):
        """Testa eliminação de documento"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        with connection.cursor() as cursor:
            id_documento = create_test_documento(cursor, self.id_associacao, self.id_tipo_documento, self.id_mandato)

        response = self.client.post(reverse('eliminar_documento', args=[id_documento]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_descarregar_documento(self):
        """Testa download de documento"""
        import os
        from django.conf import settings

        # Criar ficheiro físico primeiro
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'documentos', str(self.id_associacao))
        os.makedirs(upload_dir, exist_ok=True)
        ficheiro_path = os.path.join(upload_dir, 'teste_download.pdf')
        with open(ficheiro_path, 'wb') as f:
            f.write(b"%PDF-1.4\nteste content")

        with connection.cursor() as cursor:
            # Criar documento com o caminho do ficheiro real
            cursor.execute("""
                INSERT INTO documento (nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, id_associacao, id_mandato)
                VALUES (%s, NOW(), %s, %s, 'Observações', %s, %s, %s)
                RETURNING id_documento
            """, ['Documento Download', '2024-01-15', 'documentos/' + str(self.id_associacao) + '/teste_download.pdf',
                  self.id_tipo_documento, self.id_associacao, self.id_mandato])
            id_documento = cursor.fetchone()[0]

        response = self.client.get(reverse('descarregar_documento', args=[id_documento]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_isolamento_tipos_documento(self):
        """Testa isolamento multi-tenancy em tipos de documento"""
        # Criar outra associação
        with connection.cursor() as cursor:
            id_associacao2 = create_test_associacao(cursor, nipc='999999999', nome='Outra Associação')
            create_test_tipo_documento(cursor, id_associacao2, 'Tipo Outra')

        # Tentar aceder tipo da outra associação
        response = self.client.get(reverse('editar_tipo_documento', args=[999999]))  # ID inexistente
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_tipos_documento'))

    def test_isolamento_documentos(self):
        """Testa isolamento multi-tenancy em documentos"""
        # Criar outra associação
        with connection.cursor() as cursor:
            id_associacao2 = create_test_associacao(cursor, nipc='999999999', nome='Outra Associação')
            id_tipo2 = create_test_tipo_documento(cursor, id_associacao2, 'Tipo Outra')
            id_mandato2 = create_test_mandato(cursor, id_associacao2)
            id_documento2 = create_test_documento(cursor, id_associacao2, id_tipo2, id_mandato2)

        # Tentar aceder documento da outra associação
        response = self.client.get(reverse('editar_documento', args=[id_documento2]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('listar_documentos'))

    def test_associado_nao_acede_documentos(self):
        """Testa que associado não acede à gestão de documentos"""
        self.client.logout()
        self.client.post(reverse('login'), {
            'nipc': '987654321',
            'password': 'associado123'
        })

        response = self.client.get(reverse('listar_documentos'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/associado/', response.url)

        response = self.client.get(reverse('listar_tipos_documento'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/associado/', response.url)

    def test_tipo_documento_form_valid(self):
        """Testa TipoDocumentoForm válido"""
        from associacao.forms import TipoDocumentoForm
        form = TipoDocumentoForm(data={
            'nome_tipo_documento': 'Teste',
            'descricao_tipo_documento': 'Descrição',
            'id_associacao': self.id_associacao,
        })
        self.assertTrue(form.is_valid())

    def test_tipo_documento_form_invalid(self):
        """Testa TipoDocumentoForm inválido"""
        from associacao.forms import TipoDocumentoForm
        form = TipoDocumentoForm(data={
            'nome_tipo_documento': '',
            'descricao_tipo_documento': 'Descrição',
            'id_associacao': self.id_associacao,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('nome_tipo_documento', form.errors)

    def test_documento_form_valid(self):
        """Testa DocumentoForm válido"""
        from associacao.forms import DocumentoForm
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4\nteste content",
            content_type="application/pdf"
        )

        form = DocumentoForm(
            data={
                'nome_documento': 'Teste',
                'data_upload_0': '2024-01-15',
                'data_upload_1': '10:00',
                'data_documento': '2024-01-15',
                'observacoes': 'Obs',
                'id_tipo_documento': str(self.id_tipo_documento),
                'id_mandato': str(self.id_mandato),
                'id_associacao': self.id_associacao,
            },
            files={'ficheiro': ficheiro},
            id_associacao=self.id_associacao
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_documento_form_invalid_extension(self):
        """Testa DocumentoForm com extensão inválida"""
        from associacao.forms import DocumentoForm
        from django.core.files.uploadedfile import SimpleUploadedFile

        ficheiro = SimpleUploadedFile(
            "teste.exe",
            b"exe content",
            content_type="application/x-executable"
        )

        form = DocumentoForm(
            data={
                'nome_documento': 'Teste',
                'data_upload_0': '2024-01-15',
            'data_upload_1': '10:00',
                'data_documento': '2024-01-15',
                'observacoes': 'Obs',
                'id_tipo_documento': str(self.id_tipo_documento),
                'id_mandato': str(self.id_mandato),
                'id_associacao': self.id_associacao,
            },
            files={'ficheiro': ficheiro},
            id_associacao=self.id_associacao
        )
        self.assertFalse(form.is_valid())
        self.assertIn('ficheiro', form.errors)
