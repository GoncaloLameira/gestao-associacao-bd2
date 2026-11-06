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
        super().__init__(*args, **kwargs)

        associados = database.listar_associados()
        cargos = database.listar_cargos()
        mandatos = database.listar_mandatos_para_selecao()

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
                f'{mandato[2].strftime("%d/%m/%Y")}'
            )
            for mandato in mandatos
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
        max_length=9,
        required=False
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

    def clean(self):
        dados = super().clean()
        inicio = dados.get("data_adesao")
        fim = dados.get("data_saida")

        if inicio and fim and fim < inicio:
            raise forms.ValidationError(
                "A data de saída não pode ser anterior à data de adesão."
            )

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
        super().__init__(*args, **kwargs)

        orgaos = database.listar_orgaos_sociais_para_selecao()

        self.fields["id_orgao_social"].choices = [
            (str(orgao[0]), orgao[1])
            for orgao in orgaos
        ]


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
        super().__init__(*args, **kwargs)

        quotas = database.listar_quotas()
        self.fields['id_quota'].choices = [
            (str(quota[0]), f"{quota[1]} - {quota[2]}€ ({quota[3]})")
            for quota in quotas
        ]


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
        super().__init__(*args, **kwargs)

        associados = database.listar_associados()
        quotas = database.listar_quotas()

        self.fields['id_associado'].choices = [
            (str(associado[0]), f"#{associado[1]} - {associado[2]}")
            for associado in associados
        ]

        self.fields['id_quota'].choices = [
            (str(quota[0]), f"{quota[1]} - {quota[2]}€")
            for quota in quotas
        ]


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
        super().__init__(*args, **kwargs)

        quotas_pendentes = database.listar_quotas_associado_para_pagamento()
        movimentos = database.listar_movimentos_bancarios_para_selecao()

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
    ficheiro = forms.CharField(
        label="Ficheiro (caminho/nome)",
        max_length=255,
        help_text="Caminho ou identificador do ficheiro no sistema de armazenamento"
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        tipos_documento = database.listar_tipos_documento_para_selecao()
        mandatos = database.listar_mandatos_para_selecao()

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
