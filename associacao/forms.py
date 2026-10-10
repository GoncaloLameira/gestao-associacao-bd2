from django import forms
from . import database


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

    id_associacao = forms.IntegerField(
        label='ID da Associação',
        min_value=1
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

    tipo_via = forms.CharField(
        label='Tipo de via',
        max_length=30,
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
        required=False
    )

    id_localidade = forms.ChoiceField(
        label='Localidade',
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        localidades = database.listar_localidades()

        self.fields['id_localidade'].choices = [
            ('', 'Sem localidade')
        ] + [
            (localidade[0], localidade[1])
            for localidade in localidades
        ]


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

    tipo_via = forms.CharField(
        label="Tipo de via",
        max_length=30,
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
        required=False
    )
    id_localidade = forms.ChoiceField(
        label="Localidade",
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        localidades = database.listar_localidades()
        self.fields["id_localidade"].choices = [
            ("", "Sem localidade")
        ] + [
            (str(localidade[0]), localidade[1])
            for localidade in localidades
        ]

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
