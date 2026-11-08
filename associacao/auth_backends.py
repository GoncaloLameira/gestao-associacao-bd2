"""
Backends de autenticação personalizados para o Sistema de Gestão de Associações.

Suporta dois tipos de utilizador:
1. Direção - conta partilhada da associação (tabela associacao)
2. Associado - conta individual (tabela associado)
"""

from django.contrib.auth.hashers import check_password
from django.db import connection


class DirecaoBackend:
    """
    Backend de autenticação para a Direção.

    A Direção utiliza uma única conta partilhada da associação.
    Autentica contra a tabela `associacao` usando o NIPC e password_hash.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_associacao, nome, nipc, password_hash
                FROM associacao
                WHERE nipc = %s
                """,
                [username]
            )
            row = cursor.fetchone()

        if not row:
            return None

        id_associacao, nome, nipc, password_hash = row

        if not password_hash:
            return None

        if check_password(password, password_hash):
            # Criar um objeto utilizador simples para a Direção
            return DirecaoUser(id_associacao, nome, nipc, password_hash)

        return None

    def get_user(self, user_id):
        """Obter utilizador da Direção por ID da associação."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_associacao, nome, nipc, password_hash
                FROM associacao
                WHERE id_associacao = %s
                """,
                [user_id]
            )
            row = cursor.fetchone()

        if row:
            return DirecaoUser(*row)
        return None


class AssociadoBackend:
    """
    Backend de autenticação para Associados.

    Cada associado tem uma conta individual.
    Autentica contra a tabela `associado` usando NIF, NIPC da associação e
    password_hash. Um NIF pode legitimamente existir em mais de uma associação.
    """

    def authenticate(self, request, username=None, password=None, association_nipc=None, **kwargs):
        if not username or not password:
            return None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id_associado, a.numero_associado, a.nome, a.nif, a.password_hash, a.id_associacao,
                       exigir_alteracao_password
                FROM associado a
                JOIN associacao ass ON ass.id_associacao = a.id_associacao
                WHERE a.nif = %s AND a.estado = 'Ativo'
                  AND (%s IS NULL OR ass.nipc = %s)
                ORDER BY a.id_associado
                """,
                [username, association_nipc or None, association_nipc or None]
            )
            rows = cursor.fetchall()

        # Compatibilidade para credenciais antigas: só é seguro autenticar sem
        # NIPC quando o NIF identifica um único associado ativo.
        if len(rows) != 1:
            return None

        row = rows[0]

        id_associado, numero_associado, nome, nif, password_hash, id_associacao, exigir_alteracao_password = row

        if not password_hash:
            return None

        if check_password(password, password_hash):
            return AssociadoUser(
                id_associado, numero_associado, nome, nif, id_associacao, password_hash, exigir_alteracao_password
            )

        return None

    def get_user(self, user_id):
        """Obter associado por ID."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_associado, numero_associado, nome, nif, id_associacao,
                       password_hash, exigir_alteracao_password
                FROM associado
                WHERE id_associado = %s AND estado = 'Ativo'
                """,
                [user_id]
            )
            row = cursor.fetchone()

        if row:
            return AssociadoUser(*row)
        return None


class DirecaoUser:
    """
    Representação de um utilizador da Direção.
    Não herda de AbstractBaseUser para simplicidade - usa duck typing.
    """

    def __init__(self, id_associacao, nome, nipc, password_hash):
        self.id = id_associacao
        self.id_associacao = id_associacao
        self.nome = nome
        self.nipc = nipc
        self.password_hash = password_hash
        self.tipo = 'direcao'
        self.is_authenticated = True
        self.is_anonymous = False
        self.is_active = True
        self.is_staff = True  # Para aceder ao admin Django se necessário
        self.is_superuser = False

        # Add _meta to mimic Django model for session handling
        self._meta = self._Meta(self)

    def __str__(self):
        return f"Direção: {self.nome} ({self.nipc})"

    def has_perm(self, perm, obj=None):
        return True  # Direção tem todas as permissões administrativas

    def has_module_perms(self, app_label):
        return True

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        return self.nome.split()[0] if self.nome else ''

    def get_session_auth_hash(self):
        """Return a hash for session authentication verification."""
        import hashlib
        return hashlib.sha256(f"direcao:{self.id_associacao}:{self.password_hash}".encode()).hexdigest()

    def get_session_auth_fallback_hash(self):
        return []

    def save(self, *args, **kwargs):
        """No-op save method for Django authentication compatibility."""
        pass

    class _Meta:
        """Mimic Django's model _meta for session authentication."""
        def __init__(self, user):
            self.user = user

        class _PK:
            def value_to_string(self, user):
                return str(user.id_associacao)

        pk = _PK()


class AssociadoUser:
    """
    Representação de um associado autenticado.
    """

    def __init__(self, id_associado, numero_associado, nome, nif, id_associacao, password_hash, exigir_alteracao_password):
        self.id = id_associado
        self.id_associado = id_associado
        self.numero_associado = numero_associado
        self.nome = nome
        self.nif = nif
        self.id_associacao = id_associacao
        self.password_hash = password_hash
        self.exigir_alteracao_password = exigir_alteracao_password
        self.tipo = 'associado'
        self.is_authenticated = True
        self.is_anonymous = False
        self.is_active = True
        self.is_staff = False
        self.is_superuser = False

        # Add _meta to mimic Django model for session handling
        self._meta = self._Meta(self)

    def __str__(self):
        return f"Associado #{self.numero_associado}: {self.nome} ({self.email})"

    def has_perm(self, perm, obj=None):
        # Associados só têm permissões de leitura nos seus próprios dados
        return False

    def has_module_perms(self, app_label):
        return False

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        return self.nome.split()[0] if self.nome else ''

    def get_session_auth_hash(self):
        """Return a hash for session authentication verification."""
        import hashlib
        return hashlib.sha256(f"associado:{self.id_associado}:{self.password_hash}".encode()).hexdigest()

    def get_session_auth_fallback_hash(self):
        return []

    def save(self, *args, **kwargs):
        """No-op save method for Django authentication compatibility."""
        pass

    class _Meta:
        """Mimic Django's model _meta for session authentication."""
        def __init__(self, user):
            self.user = user

        class _PK:
            def value_to_string(self, user):
                return str(user.id_associado)

        pk = _PK()
