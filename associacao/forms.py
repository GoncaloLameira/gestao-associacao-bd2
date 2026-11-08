from django import forms
from . import database

# Tipos de via portugueses (shared)
TIPOS_VIA_CHOICES = [
    ('', 'Selecione...'),
    ('Rua', 'Rua'),
    ('Avenida', 'Avenida'),
    ('Travessa', 'Travessa'),
    ('Largo', 'Largo'),
    ('Praça', 'Praça'),
    ('Alameda', 'Alameda'),
    ('Estrada', 'Estrada'),
    ('Caminho', 'Caminho'),
    ('Beco', 'Beco'),
    ('Calçada', 'Calçada'),
]


class MandatoForm(forms.Form):
    data_inicio = forms.DateField(
        label='Data de início',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    data_fim = forms.DateField(
        label="Data de fim",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"})
    )


class ExercicioCargoForm(forms.Form):
    data_inicio = forms.DateField(
        label='Data de início',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    data_fim = forms.DateField(
        label='Data de fim',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    id_associado = forms.ChoiceField(
        label='Associado'
    )

    id_cargo = forms.ChoiceField(
        label='Cargo'
    )

    id_mandato = forms.ChoiceField(
        label='Mandato'
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)

        associados = database.listar_associados_para_selecao(id_associacao)
        cargos = database.listar_cargos(id_associacao)
        mandatos = database.listar_mandatos_para_selecao(id_associacao)

        self.fields['id_associado'].choices = [
            (associado[0], associado[1])
            for associado in associados
        ]

        self.fields['id_cargo'].choices = [
            (
                cargo[0],
                f'{cargo[1]} - {cargo[2]}'
            )
            for cargo in cargos
        ]

        self.fields['id_mandato'].choices = [
            (
                mandato[0],
                f'{mandato[1].strftime("%d/%m/%Y")} - '
                f'{mandato[2].strftime("%d/%m/%Y") if mandato[2] else "em vigor"}'
            )
            for mandato in mandatos
        ]


class AlterarPalavraPasseForm(forms.Form):
    palavra_passe_atual = forms.CharField(label='Palavra-passe atual', widget=forms.PasswordInput)
    nova_palavra_passe = forms.CharField(label='Nova palavra-passe', min_length=12, widget=forms.PasswordInput)
    confirmacao = forms.CharField(label='Confirmar nova palavra-passe', widget=forms.PasswordInput)

    def clean(self):
        dados = super().clean()
        if dados.get('nova_palavra_passe') != dados.get('confirmacao'):
            self.add_error('confirmacao', 'A confirmação não corresponde à nova palavra-passe.')
        return dados


class PassagemPosseForm(forms.Form):
    id_mandato_anterior = forms.ChoiceField(label='Mandato anterior')
    data_inicio = forms.DateField(label='Início do novo mandato', widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(label='Fim do novo mandato', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    id_presidente = forms.ChoiceField(label='Novo presidente')

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao')
        super().__init__(*args, **kwargs)
        mandatos = database.listar_mandatos(id_associacao)
        associados = database.listar_associados_para_selecao(id_associacao)
        cargos = database.listar_cargos_completos(id_associacao)
        self.fields['id_mandato_anterior'].choices = [
            (str(mandato[0]), f'{mandato[1]} — {mandato[2] or "em vigor"}') for mandato in mandatos
        ]
        associado_choices = [(str(associado[0]), f'#{associado[1]} - {associado[2]}') for associado in associados]
        self.fields['id_presidente'].choices = associado_choices
        self.cargos = cargos
        for cargo in cargos:
            self.fields[f'cargo_{cargo[0]}'] = forms.ChoiceField(
                label=f'{cargo[1]} ({cargo[3]})', choices=associado_choices,
            )

    def composicao(self):
        return [
            {'id_cargo': cargo[0], 'id_associado': int(self.cleaned_data[f'cargo_{cargo[0]}'])}
            for cargo in self.cargos
        ]


# ==========================================
# FORMULÁRIO: ASSOCIACAO
# ==========================================

class AssociacaoForm(forms.Form):
    nipc = forms.CharField(
        label='NIPC',
        max_length=9,
        min_length=9
    )

    nome = forms.CharField(
        label='Nome da associação',
        max_length=150
    )

    data_fundacao = forms.DateField(
        label='Data de fundação',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    email = forms.EmailField(
        label='Email',
        required=False
    )

    telefone = forms.CharField(
        label='Telefone',
        max_length=20,
        required=False
    )

    password = forms.CharField(
        label='Palavra-passe',
        widget=forms.PasswordInput
    )

    tipo_via = forms.ChoiceField(
        label='Tipo de via',
        choices=TIPOS_VIA_CHOICES,
        required=False
    )

    nome_via = forms.CharField(
        label='Nome da via',
        max_length=150,
        required=False
    )

    numero_porta = forms.CharField(
        label='Número da porta',
        max_length=20,
        required=False
    )

    andar = forms.CharField(
        label='Andar',
        max_length=20,
        required=False
    )

    codigo_postal = forms.CharField(
        label='Código postal',
        max_length=8,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '0000-000',
            'pattern': '\\d{4}-\\d{3}',
            'title': 'Formato: 0000-000'
        })
    )

    id_localidade = forms.IntegerField(
        label='Localidade',
        required=False,
        widget=forms.HiddenInput()
    )

    localidade = forms.CharField(
        label='Localidade',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'readonly': 'readonly',
            'placeholder': 'Preenchido automaticamente'
        })
    )


# ==========================================
# FORMULÁRIO: EVENTO
# ==========================================

class EventoForm(forms.Form):
    nome_evento = forms.CharField(
        label='Nome do evento',
        max_length=100
    )

    descricao_evento = forms.CharField(
        label='Descrição',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )

    data_inicio_evento = forms.SplitDateTimeField(
        label='Data e hora de início',
        widget=forms.SplitDateTimeWidget(
            date_attrs={'type': 'date'},
            time_attrs={'type': 'time'}
        )
    )

    data_fim_evento = forms.SplitDateTimeField(
        label='Data e hora de fim',
        required=False,
        widget=forms.SplitDateTimeWidget(
            date_attrs={'type': 'date'},
            time_attrs={'type': 'time'}
        )
    )

    local_evento = forms.CharField(
        label='Local',
        max_length=100,
        required=False
    )

    estado_evento = forms.ChoiceField(
        label='Estado',
        choices=[
            ('Planeado', 'Planeado'),
            ('Em curso', 'Em curso'),
            ('Concluído', 'Concluído'),
            ('Cancelado', 'Cancelado')
        ]
    )

    def clean(self):
        dados = super().clean()

        inicio = dados.get('data_inicio_evento')
        fim = dados.get('data_fim_evento')

        if inicio and fim and fim < inicio:
            self.add_error(
                'data_fim_evento',
                'A data de fim não pode ser anterior à data de início.'
            )

        return dados


# ==========================================
# FORMULÁRIO ASSOCIADO
# ==========================================

class AssociadoForm(forms.Form):
    numero_associado = forms.IntegerField(
        label="Número de associado",
        min_value=1
    )
    nome = forms.CharField(
        label="Nome",
        max_length=150
    )
    nif = forms.CharField(
        label="NIF",
        max_length=9
    )
    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False
    )
    email = forms.EmailField(
        label="Email",
        required=False
    )
    telefone = forms.CharField(
        label="Telefone",
        max_length=20,
        required=False
    )
    data_adesao = forms.DateField(
        label="Data de adesão",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    data_saida = forms.DateField(
        label="Data de saída",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False
    )
    estado = forms.ChoiceField(
        label="Estado",
        choices=[
            ("Ativo", "Ativo"),
            ("Inativo", "Inativo"),
            ("Suspenso", "Suspenso")
        ]
    )
    password = forms.CharField(
        label="Palavra-passe",
        widget=forms.PasswordInput,
        required=False,
        help_text="Deixe em branco para manter a palavra-passe atual (edição) ou definir nova (registo)"
    )

    tipo_via = forms.ChoiceField(
        label="Tipo de via",
        choices=TIPOS_VIA_CHOICES,
        required=False
    )
    nome_via = forms.CharField(
        label="Nome da via",
        max_length=150,
        required=False
    )
    numero_porta = forms.CharField(
        label="Número da porta",
        max_length=20,
        required=False
    )
    andar = forms.CharField(
        label="Andar",
        max_length=20,
        required=False
    )
    codigo_postal = forms.CharField(
        label="Código postal",
        max_length=8,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '0000-000',
            'pattern': '\\d{4}-\\d{3}',
            'title': 'Formato: 0000-000'
        })
    )

    id_localidade = forms.IntegerField(
        label="Localidade",
        required=False,
        widget=forms.HiddenInput()
    )

    localidade = forms.CharField(
        label="Localidade",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'readonly': 'readonly',
            'placeholder': 'Preenchido automaticamente'
        })
    )

    def __init__(self, *args, **kwargs):
        # Accept id_associacao for consistency with other forms, but don't use it
        # since the association is determined by the logged-in user
        kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        dados = super().clean()
        inicio = dados.get("data_adesao")
        fim = dados.get("data_saida")

        if inicio and fim and fim < inicio:
            raise forms.ValidationError(
                "A data de saída não pode ser anterior à data de adesão."
            )

        return dados


class DefinirPalavraPasseAssociadoForm(forms.Form):
    nova_palavra_passe = forms.CharField(label='Nova palavra-passe', min_length=12, widget=forms.PasswordInput)
    confirmacao = forms.CharField(label='Confirmar nova palavra-passe', widget=forms.PasswordInput)

    def clean(self):
        dados = super().clean()
        if dados.get('nova_palavra_passe') != dados.get('confirmacao'):
            self.add_error('confirmacao', 'A confirmação não corresponde à nova palavra-passe.')
        return dados


class PerfilAssociadoForm(forms.Form):
    """Dados pessoais partilhados pelo mesmo associado entre associações."""

    nome = forms.CharField(label='Nome completo', max_length=150)
    data_nascimento = forms.DateField(
        label='Data de nascimento', required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    email = forms.EmailField(label='Email', required=False)
    telefone = forms.CharField(label='Telefone', max_length=20, required=False)
    tipo_via = forms.ChoiceField(label='Tipo de via', choices=TIPOS_VIA_CHOICES, required=False)
    nome_via = forms.CharField(label='Nome da via', max_length=150, required=False)
    numero_porta = forms.CharField(label='Número da porta', max_length=20, required=False)
    andar = forms.CharField(label='Andar', max_length=20, required=False)
    codigo_postal = forms.CharField(
        label='Código postal', max_length=8, required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '0000-000', 'pattern': '\\d{4}-\\d{3}',
            'title': 'Formato: 0000-000'
        })
    )
    id_localidade = forms.IntegerField(required=False, widget=forms.HiddenInput())
    localidade = forms.CharField(
        label='Localidade', max_length=100, required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'placeholder': 'Preenchido automaticamente'})
    )
    palavra_passe_atual = forms.CharField(
        label='Palavra-passe atual', required=False, widget=forms.PasswordInput,
        help_text='Obrigatória apenas para alterar a palavra-passe.'
    )
    nova_palavra_passe = forms.CharField(
        label='Nova palavra-passe', required=False, min_length=12, widget=forms.PasswordInput
    )
    confirmacao_palavra_passe = forms.CharField(
        label='Confirmar nova palavra-passe', required=False, widget=forms.PasswordInput
    )

    def clean(self):
        dados = super().clean()
        password_fields = ('palavra_passe_atual', 'nova_palavra_passe', 'confirmacao_palavra_passe')
        if any(dados.get(field) for field in password_fields):
            if not all(dados.get(field) for field in password_fields):
                raise forms.ValidationError('Preencha os três campos para alterar a palavra-passe.')
            if dados['nova_palavra_passe'] != dados['confirmacao_palavra_passe']:
                self.add_error('confirmacao_palavra_passe', 'A confirmação não corresponde à nova palavra-passe.')
        return dados


# ==========================================
# FORMULÁRIO QUOTA
# ==========================================

class QuotaForm(forms.Form):
    designacao_quota = forms.CharField(
        label="Designação da quota",
        max_length=100
    )
    valor_quota = forms.FloatField(
        label="Valor da quota",
        min_value=0.01
    )
    periodicidade_quota = forms.ChoiceField(
        label="Periodicidade",
        choices=[
            ("Mensal", "Mensal"),
            ("Trimestral", "Trimestral"),
            ("Semestral", "Semestral"),
            ("Anual", "Anual")
        ]
    )
    data_inicio_quota = forms.DateField(
        label="Data de início",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    data_fim_quota = forms.DateField(
        label="Data de fim",
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False
    )

    def clean(self):
        dados = super().clean()
        inicio = dados.get("data_inicio_quota")
        fim = dados.get("data_fim_quota")

        if inicio and fim and fim < inicio:
            raise forms.ValidationError(
                "A data de fim não pode ser anterior à data de início."
            )

        return dados


# ==========================================
# FORMULÁRIO ÓRGÃO SOCIAL
# ==========================================

class OrgaoSocialForm(forms.Form):
    nome = forms.CharField(
        label="Nome do órgão social",
        max_length=100
    )

    descricao = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )


# ==========================================
# FORMULÁRIO CARGO
# ==========================================

class CargoForm(forms.Form):
    nome = forms.CharField(
        label="Nome do cargo",
        max_length=100
    )

    descricao = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )

    id_orgao_social = forms.ChoiceField(
        label="Órgão social"
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao

        orgaos = database.listar_orgaos_sociais_para_selecao(id_associacao) if id_associacao else []

        self.fields["id_orgao_social"].choices = [
            (str(orgao[0]), orgao[1])
            for orgao in orgaos
        ]

    def clean_id_orgao_social(self):
        id_orgao_social = self.cleaned_data.get('id_orgao_social')
        if id_orgao_social and self.id_associacao:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT id_associacao FROM orgao_social WHERE id_orgao_social = %s", [int(id_orgao_social)])
                row = cursor.fetchone()
                if not row or row[0] != self.id_associacao:
                    raise forms.ValidationError('Órgão social não pertence a esta associação.')
        return id_orgao_social


# ==========================================
# FORMULÁRIO: GERAR QUOTAS ASSOCIADOS
# ==========================================

class GerarQuotasForm(forms.Form):
    id_quota = forms.ChoiceField(
        label="Quota"
    )

    data_vencimento_inicial = forms.DateField(
        label="Data de vencimento inicial",
        widget=forms.DateInput(attrs={"type": "date"})
    )

    periodos = forms.IntegerField(
        label="Número de períodos",
        min_value=1,
        max_value=60,
        initial=12,
        help_text="Número de quotas a gerar (ex: 12 para 1 ano de quotas mensais)"
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao

        quotas = database.listar_quotas(id_associacao) if id_associacao else []
        self.fields['id_quota'].choices = [
            (str(quota[0]), f"{quota[1]} - {quota[2]}€ ({quota[3]})")
            for quota in quotas
        ]

    def clean_id_quota(self):
        id_quota = self.cleaned_data.get('id_quota')
        if id_quota and self.id_associacao:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT id_associacao FROM quota WHERE id_quota = %s", [int(id_quota)])
                row = cursor.fetchone()
                if not row or row[0] != self.id_associacao:
                    raise forms.ValidationError('Quota não pertence a esta associação.')
        return id_quota


# ==========================================
# FORMULÁRIO: QUOTA ASSOCIADO
# ==========================================

class QuotaAssociadoForm(forms.Form):
    valor_devido = forms.DecimalField(
        label="Valor devido",
        max_digits=10,
        decimal_places=2,
        min_value=0
    )

    data_vencimento = forms.DateField(
        label="Data de vencimento",
        widget=forms.DateInput(attrs={"type": "date"})
    )

    periodo_referencia = forms.CharField(
        label="Período de referência",
        max_length=20
    )

    estado_quota_associado = forms.ChoiceField(
        label="Estado",
        choices=[
            ("Pendente", "Pendente"),
            ("Pago", "Pago"),
            ("Parcial", "Parcial"),
            ("Em Dívida", "Em Dívida"),
            ("Isento", "Isento")
        ]
    )

    id_associado = forms.ChoiceField(
        label="Associado"
    )

    id_quota = forms.ChoiceField(
        label="Quota"
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao

        associados = database.listar_associados_para_selecao(id_associacao) if id_associacao else []
        quotas = database.listar_quotas(id_associacao) if id_associacao else []

        self.fields['id_associado'].choices = [
            (str(associado[0]), f"#{associado[1]} - {associado[2]}")
            for associado in associados
        ]

        self.fields['id_quota'].choices = [
            (str(quota[0]), f"{quota[1]} - {quota[2]}€")
            for quota in quotas
        ]

    def clean(self):
        dados = super().clean()
        
        # Validação cruzada
        if self.id_associacao:
            from django.db import connection
            with connection.cursor() as cursor:
                id_associado = dados.get('id_associado')
                id_quota = dados.get('id_quota')
                
                if id_associado:
                    cursor.execute("SELECT id_associacao FROM associado WHERE id_associado = %s", [int(id_associado)])
                    row = cursor.fetchone()
                    if not row or row[0] != self.id_associacao:
                        self.add_error('id_associado', 'Associado não pertence a esta associação.')
                
                if id_quota:
                    cursor.execute("SELECT id_associacao FROM quota WHERE id_quota = %s", [int(id_quota)])
                    row = cursor.fetchone()
                    if not row or row[0] != self.id_associacao:
                        self.add_error('id_quota', 'Quota não pertence a esta associação.')

        return dados


# ==========================================
# FORMULÁRIO: MOVIMENTO BANCÁRIO
# ==========================================

class MovimentoBancarioForm(forms.Form):
    data_movimento = forms.DateField(
        label="Data do movimento",
        widget=forms.DateInput(attrs={"type": "date"})
    )
    descricao_movimento = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )
    valor_movimento = forms.DecimalField(
        label="Valor",
        max_digits=10,
        decimal_places=2
    )
    referencia_movimento = forms.CharField(
        label="Referência",
        max_length=100,
        required=False
    )


# ==========================================
# FORMULÁRIO: PAGAMENTO
# ==========================================

class PagamentoForm(forms.Form):
    data_pagamento = forms.SplitDateTimeField(
        label="Data e hora do pagamento",
        widget=forms.SplitDateTimeWidget(
            date_attrs={'type': 'date'},
            time_attrs={'type': 'time'}
        )
    )
    valor_pago = forms.DecimalField(
        label="Valor pago",
        max_digits=10,
        decimal_places=2,
        min_value=0.01
    )
    metodo_pagamento = forms.ChoiceField(
        label="Método de pagamento",
        choices=[
            ("Dinheiro", "Dinheiro"),
            ("Transferência", "Transferência"),
            ("MB Way", "MB Way"),
            ("Multibanco", "Multibanco"),
            ("Cheque", "Cheque"),
            ("Outro", "Outro")
        ]
    )
    referencia_pagamento = forms.CharField(
        label="Referência",
        max_length=100,
        required=False
    )
    id_quota_associado = forms.ChoiceField(
        label="Quota do associado"
    )
    id_movimento = forms.ChoiceField(
        label="Movimento bancário (opcional)",
        required=False
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao

        quotas_pendentes = database.listar_quotas_associado_para_pagamento(id_associacao) if id_associacao else []
        movimentos = database.listar_movimentos_bancarios_para_selecao(id_associacao) if id_associacao else []

        self.fields['id_quota_associado'].choices = [
            (str(qa[0]), f"#{qa[2]} - {qa[1]} - {qa[3]} - {qa[4]} - {qa[5]}€ ({qa[6]})")
            for qa in quotas_pendentes
        ]

        self.fields['id_movimento'].choices = [
            ('', 'Sem movimento bancário associado')
        ] + [
            (str(m[0]), f"{m[1]} - {m[2]} - {m[3]}€")
            for m in movimentos
        ]

    def clean(self):
        dados = super().clean()
        
        # Validação cruzada
        if self.id_associacao:
            from django.db import connection
            with connection.cursor() as cursor:
                id_quota_associado = dados.get('id_quota_associado')
                id_movimento = dados.get('id_movimento')
                
                if id_quota_associado:
                    cursor.execute("""
                        SELECT q.id_associacao 
                        FROM quota_associado qa
                        JOIN quota q ON qa.id_quota = q.id_quota
                        WHERE qa.id_quota_associado = %s
                    """, [int(id_quota_associado)])
                    row = cursor.fetchone()
                    if not row or row[0] != self.id_associacao:
                        self.add_error('id_quota_associado', 'Quota do associado não pertence a esta associação.')
                
                if id_movimento:
                    cursor.execute("""
                        SELECT q.id_associacao
                        FROM movimento_bancario mb
                        LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
                        LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
                        LEFT JOIN quota q ON qa.id_quota = q.id_quota
                        WHERE mb.id_movimento = %s
                    """, [int(id_movimento)])
                    row = cursor.fetchone()
                    if not row or row[0] != self.id_associacao:
                        self.add_error('id_movimento', 'Movimento bancário não pertence a esta associação.')

        return dados


# ==========================================
# FORMULÁRIO: TIPO DOCUMENTO
# ==========================================

class TipoDocumentoForm(forms.Form):
    nome_tipo_documento = forms.CharField(
        label="Nome do tipo de documento",
        max_length=150
    )
    descricao_tipo_documento = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )
    id_associacao = forms.IntegerField(
        label="ID da Associação",
        min_value=1,
        widget=forms.HiddenInput()
    )


# ==========================================
# FORMULÁRIO: DOCUMENTO
# ==========================================

class DocumentoForm(forms.Form):
    nome_documento = forms.CharField(
        label="Nome do documento",
        max_length=150
    )
    data_upload = forms.SplitDateTimeField(
        label="Data e hora do upload",
        widget=forms.SplitDateTimeWidget(
            date_attrs={'type': 'date'},
            time_attrs={'type': 'time'}
        )
    )
    data_documento = forms.DateField(
        label="Data do documento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"})
    )
    ficheiro = forms.FileField(
        label="Ficheiro",
        help_text="Formatos permitidos: PDF, DOC, DOCX, XLS, XLSX, JPG, PNG. Tamanho máximo: 10MB",
        required=False  # Opcional para edição
    )
    observacoes = forms.CharField(
        label="Observações",
        max_length=400,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3})
    )
    id_tipo_documento = forms.ChoiceField(
        label="Tipo de documento"
    )
    id_associacao = forms.IntegerField(
        label="ID da Associação",
        min_value=1,
        widget=forms.HiddenInput()
    )
    id_mandato = forms.ChoiceField(
        label="Mandato (opcional)",
        required=False
    )

    # Extensões permitidas
    EXTENSOES_PERMITIDAS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']
    TAMANHO_MAXIMO = 10 * 1024 * 1024  # 10MB

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        editing = kwargs.pop('editing', False)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao
        self.editing = editing

        # Se estiver a editar, o ficheiro não é obrigatório
        if editing:
            self.fields['ficheiro'].required = False

        tipos_documento = database.listar_tipos_documento_para_selecao(id_associacao) if id_associacao else []
        mandatos = database.listar_mandatos_para_selecao(id_associacao) if id_associacao else []

        self.fields['id_tipo_documento'].choices = [
            (str(td[0]), td[1])
            for td in tipos_documento
        ]

        self.fields['id_mandato'].choices = [
            ('', 'Sem mandato associado')
        ] + [
            (str(m[0]), f"{m[1].strftime('%d/%m/%Y')} - {m[2].strftime('%d/%m/%Y') if m[2] else 'Em vigor'}")
            for m in mandatos
        ]

    def clean_ficheiro(self):
        """Valida o ficheiro carregado."""
        ficheiro = self.cleaned_data.get('ficheiro')

        # Se estiver a editar e não foi fornecido ficheiro, não validar
        if self.editing and not ficheiro:
            return ficheiro

        # Para novo registo, ou se ficheiro foi fornecido na edição, validar
        if not ficheiro:
            raise forms.ValidationError("O ficheiro é obrigatório.")

        # Validar extensão
        import os
        ext = os.path.splitext(ficheiro.name)[1].lower()
        if ext not in self.EXTENSOES_PERMITIDAS:
            raise forms.ValidationError(
                f"Extensão '{ext}' não permitida. "
                f"Extensões permitidas: {', '.join(self.EXTENSOES_PERMITIDAS)}"
            )

        # Validar tamanho
        if ficheiro.size > self.TAMANHO_MAXIMO:
            raise forms.ValidationError(
                f"Ficheiro demasiado grande. Tamanho máximo: {self.TAMANHO_MAXIMO // (1024*1024)}MB"
            )

        # Validar tipo MIME
        import magic
        try:
            ficheiro.seek(0)
            mime_type = magic.from_buffer(ficheiro.read(2048), mime=True)
            ficheiro.seek(0)

            MIME_TYPES_PERMITIDOS = {
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'image/jpeg',
                'image/png',
            }

            if mime_type not in MIME_TYPES_PERMITIDOS:
                raise forms.ValidationError(
                    f"Tipo de ficheiro não permitido: {mime_type}. "
                    "Apenas PDF, DOC, DOCX, XLS, XLSX, JPG, PNG são aceites."
                )
        except ImportError:
            # Se python-magic não estiver disponível, avisa mas não bloqueia
            pass

        return ficheiro

    def clean(self):
        dados = super().clean()

        # Validação cruzada
        if self.id_associacao:
            from django.db import connection
            with connection.cursor() as cursor:
                id_tipo_documento = dados.get('id_tipo_documento')
                id_mandato = dados.get('id_mandato')

                if id_tipo_documento:
                    cursor.execute("SELECT id_associacao FROM tipo_documento WHERE id_tipo_documento = %s", [int(id_tipo_documento)])
                    row = cursor.fetchone()
                    if not row or row[0] != self.id_associacao:
                        self.add_error('id_tipo_documento', 'Tipo de documento não pertence a esta associação.')

                if id_mandato:
                    cursor.execute("SELECT id_associacao FROM mandato WHERE id_mandato = %s", [int(id_mandato)])
                    row = cursor.fetchone()
                    if not row or row[0] != self.id_associacao:
                        self.add_error('id_mandato', 'Mandato não pertence a esta associação.')

        return dados


# ==========================================
# FASE 2.2 — IMPORTAÇÃO E CONCILIAÇÃO BANCÁRIA
# ==========================================

class ImportarCSVForm(forms.Form):
    """Formulário para upload de arquivo CSV de movimentos bancários."""
    arquivo_csv = forms.FileField(
        label="Arquivo CSV",
        help_text="Formato: data_movimento,descricao_movimento,valor_movimento,referencia_movimento (cabeçalho obrigatório)"
    )
    delimitador = forms.ChoiceField(
        label="Delimitador",
        choices=[
            (',', 'Vírgula (,)'),
            (';', 'Ponto e vírgula (;)'),
            ('\t', 'Tabulação (TAB)'),
        ],
        initial=',',
        required=False,
        help_text="Separador de campos no CSV"
    )
    tem_cabecalho = forms.BooleanField(
        label="Primeira linha é cabeçalho",
        initial=True,
        required=False,
        help_text="Se o arquivo contém linha de cabeçalho com nomes das colunas"
    )

    def clean(self):
        cleaned_data = super().clean()
        # Default delimitador to ',' if not explicitly provided
        if 'delimitador' not in self.data:
            cleaned_data['delimitador'] = ','
        # Default tem_cabecalho to True if not explicitly provided (checkbox not in POST)
        # Common case: CSVs have headers
        if 'tem_cabecalho' not in self.data:
            cleaned_data['tem_cabecalho'] = True
        return cleaned_data

    def clean_arquivo_csv(self):
        arquivo = self.cleaned_data['arquivo_csv']

        # Validar extensão
        if not arquivo.name.endswith('.csv'):
            raise forms.ValidationError('O arquivo deve ter extensão .csv')

        # Validar tamanho (máx 2MB)
        if arquivo.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Arquivo muito grande. Tamanho máximo: 2MB')

        # Validar conteúdo (tentar ler como texto)
        try:
            conteudo = arquivo.read().decode('utf-8')
            arquivo.seek(0)  # Reset pointer
        except UnicodeDecodeError:
            try:
                conteudo = arquivo.read().decode('latin-1')
                arquivo.seek(0)
            except UnicodeDecodeError:
                raise forms.ValidationError('Não foi possível ler o arquivo. Use codificação UTF-8 ou Latin-1')

        # Validar que tem conteúdo
        linhas = [l.strip() for l in conteudo.split('\n') if l.strip()]
        if len(linhas) < 2:  # Pelo menos cabeçalho + 1 linha
            raise forms.ValidationError('Arquivo CSV vazio ou apenas com cabeçalho')

        return arquivo


class ConciliarForm(forms.Form):
    """Formulário para confirmar conciliação entre movimento e pagamento."""
    id_movimento = forms.IntegerField(widget=forms.HiddenInput())
    id_pagamento = forms.IntegerField(widget=forms.HiddenInput())
    forcar = forms.BooleanField(
        label="Forçar conciliação (valores diferentes)",
        required=False,
        help_text="Marcar para permitir conciliar mesmo se valores não coincidirem exatamente"
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao


class DesfazerConciliacaoForm(forms.Form):
    """Formulário para desfazer conciliação."""
    id_conciliacao = forms.IntegerField(widget=forms.HiddenInput())
    motivo = forms.CharField(
        label="Motivo da reversão",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ex: Erro na conciliação, pagamento duplicado, etc.'}),
        help_text="Opcional: descreva o motivo da reversão para auditoria"
    )
    confirmar = forms.BooleanField(
        label="Confirmo que quero desfazer esta conciliação",
        required=True,
        help_text="Esta ação remove a ligação ativa entre o movimento bancário e o pagamento, mas preserva o histórico"
    )

    def __init__(self, *args, **kwargs):
        id_associacao = kwargs.pop('id_associacao', None)
        super().__init__(*args, **kwargs)
        self.id_associacao = id_associacao


class FiltroMovimentosForm(forms.Form):
    """Formulário para filtrar movimentos na lista de conciliação."""
    estado = forms.ChoiceField(
        label="Estado",
        choices=[
            ('', 'Todos'),
            ('pendente', 'Pendentes (sem conciliação)'),
            ('conciliado', 'Conciliados'),
        ],
        required=False,
        initial='pendente'
    )
    data_inicio = forms.DateField(
        label="Data início",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    data_fim = forms.DateField(
        label="Data fim",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    pesquisa = forms.CharField(
        label="Pesquisar",
        required=False,
        help_text="Pesquisar por descrição, referência ou valor"
    )
