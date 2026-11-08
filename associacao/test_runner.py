"""
Custom test runner that applies SQL schema to the test database.
"""
import os
import re
from django.test.runner import DiscoverRunner
from django.db import connection


class SQLSchemaTestRunner(DiscoverRunner):
    """
    Test runner that applies SQL schema files to the test database
    after it's created.
    """

    def setup_databases(self, **kwargs):
        # Call parent to create test database
        import sys
        sys.stderr.write("DEBUG: setup_databases called\n")
        sys.stderr.flush()
        old_config = super().setup_databases(**kwargs)
        sys.stderr.write(f"DEBUG: Parent setup_databases returned, old_config={old_config}\n")
        sys.stderr.flush()

        # Apply SQL schema to test database
        sys.stderr.write("DEBUG: Applying SQL schema to test database\n")
        sys.stderr.flush()
        self._apply_sql_schema()

        return old_config

    def _apply_sql_schema(self):
        """Apply all SQL schema files to the test database."""
        print("DEBUG: _apply_sql_schema started")
        sql_dir = os.path.join(os.path.dirname(__file__), '..', 'sql')
        sql_files = [
            '01_tabelas.sql',
            '02_procedures.sql',
            '03_views.sql',
            '04_alter_associado_password.sql',
            '05_functions.sql',
            '06_triggers.sql',
            '07_seed_localidades.sql',
            '09_migration_movimento_bancario_associacao.sql',
            '10_fase21_financeiro.sql',
            '11_migration_recalcular_estados_quotas.sql',
            '12_fase22_conciliacao_bancaria.sql',
            '13_fase25_mandatos_posse.sql',
            '14_primeiro_acesso_associado.sql',
            '15_isolamento_unicidade_associacoes.sql',
        ]

        from django.db import connection
        print(f"DEBUG: Using connection {connection}")
        with connection.cursor() as cursor:
            for sql_file in sql_files:
                sql_path = os.path.join(sql_dir, sql_file)
                print(f"DEBUG: Checking {sql_path}")
                if os.path.exists(sql_path):
                    print(f"DEBUG: Applying {sql_file}")
                    with open(sql_path, 'r') as f:
                        sql_content = f.read()

                    statements = self._split_sql_statements(sql_content)
                    print(f"DEBUG: {sql_file} split into {len(statements)} statements")

                    for statement in statements:
                        statement = statement.strip()
                        if statement:
                            try:
                                cursor.execute(statement)
                            except Exception as e:
                                print(f"SQL Error in {sql_file}: {e}")
                                print(f"Statement: {statement[:200]}")
                                pass

    def _split_sql_statements(self, sql_content):
        """
        Split SQL content into individual statements.
        Handles dollar-quoted strings (PostgreSQL functions) properly.
        Handles line comments (--) and block comments (/* */).
        Skips comment-only statements.
        """
        statements = []
        current_statement = []
        in_dollar_quote = False
        dollar_tag = None
        in_line_comment = False
        in_block_comment = False
        i = 0

        while i < len(sql_content):
            char = sql_content[i]
            next_char = sql_content[i+1] if i+1 < len(sql_content) else ''

            # Check for dollar quote start/end ($tag$)
            if char == '$' and not in_dollar_quote and not in_line_comment and not in_block_comment:
                # Look ahead for tag
                j = i + 1
                tag = '$'
                while j < len(sql_content) and sql_content[j] != '$':
                    tag += sql_content[j]
                    j += 1
                if j < len(sql_content) and sql_content[j] == '$':
                    tag += '$'
                    in_dollar_quote = True
                    dollar_tag = tag
                    current_statement.append(tag)
                    i = j + 1
                    continue

            elif char == '$' and in_dollar_quote:
                # Check if this ends the dollar quote
                if dollar_tag is not None and sql_content[i:i+len(dollar_tag)] == dollar_tag:
                    current_statement.append(dollar_tag)
                    in_dollar_quote = False
                    tag_len = len(dollar_tag)
                    dollar_tag = None
                    i += tag_len
                    continue
                else:
                    # Not the end tag, just add the $ and continue
                    current_statement.append(char)
                    i += 1
                    continue

            # Handle line comment start (--)
            elif char == '-' and next_char == '-' and not in_dollar_quote and not in_block_comment:
                in_line_comment = True
                current_statement.append(char)
                current_statement.append(next_char)
                i += 2
                continue

            # Handle line comment end (newline)
            elif char == '\n' and in_line_comment:
                in_line_comment = False
                current_statement.append(char)
                i += 1
                continue

            # Handle block comment start (/*)
            elif char == '/' and next_char == '*' and not in_dollar_quote and not in_line_comment:
                in_block_comment = True
                current_statement.append(char)
                current_statement.append(next_char)
                i += 2
                continue

            # Handle block comment end (*/)
            elif char == '*' and next_char == '/' and in_block_comment:
                in_block_comment = False
                current_statement.append(char)
                current_statement.append(next_char)
                i += 2
                continue

            # Handle semicolon as statement terminator (outside quotes and comments)
            elif char == ';' and not in_dollar_quote and not in_line_comment and not in_block_comment:
                current_statement.append(char)
                statement = ''.join(current_statement).strip()
                # Skip comment-only statements
                if statement and not self._is_comment_only(statement):
                    statements.append(statement)
                current_statement = []
                i += 1
                continue

            current_statement.append(char)
            i += 1

        # Add any remaining statement
        if current_statement:
            statement = ''.join(current_statement).strip()
            if statement and not self._is_comment_only(statement):
                statements.append(statement)

        return statements

    def _is_comment_only(self, statement):
        """Check if a statement contains only comments (no executable SQL)."""
        # Remove whitespace
        stripped = statement.strip()
        # Check if every non-empty line starts with -- or /* or is empty
        # But also check if there's any executable SQL after comments
        lines = stripped.split('\n')
        has_executable = False
        for line in lines:
            line = line.strip()
            if line and not line.startswith('--') and not line.startswith('/*'):
                has_executable = True
                break
        return not has_executable
