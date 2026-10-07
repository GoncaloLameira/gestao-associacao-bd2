from django import forms
from . import database


class MandatoForm(forms.Form):
    data_inicio = forms.DateField(
        label='Data de início',
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    data_fim = forms.DateField(
        label='Data de fim',
        widget=forms.DateInput(attrs={'type': 'date'})
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