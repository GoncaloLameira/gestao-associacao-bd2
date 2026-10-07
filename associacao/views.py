from django.shortcuts import render, redirect

from . import database
from .forms import MandatoForm, ExercicioCargoForm


def registar_mandato(request):
    if request.method == 'POST':
        form = MandatoForm(request.POST)

        if form.is_valid():
            database.inserir_mandato(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                form.cleaned_data['id_associacao']
            )

            return redirect('listar_mandatos')

    else:
        form = MandatoForm()

    return render(
        request,
        'associacao/registar_mandato.html',
        {'form': form}
    )


def listar_mandatos(request):
    mandatos = database.listar_mandatos()

    return render(
        request,
        'associacao/listar_mandatos.html',
        {'mandatos': mandatos}
    )


def registar_exercicio_cargo(request):
    if request.method == 'POST':
        form = ExercicioCargoForm(request.POST)

        if form.is_valid():
            database.inserir_exercicio_cargo(
                form.cleaned_data['data_inicio'],
                form.cleaned_data['data_fim'],
                int(form.cleaned_data['id_associado']),
                int(form.cleaned_data['id_cargo']),
                int(form.cleaned_data['id_mandato'])
)

            return redirect('listar_exercicios_cargo')

    else:
        form = ExercicioCargoForm()

    return render(
        request,
        'associacao/registar_exercicio_cargo.html',
        {'form': form}
    )


def listar_exercicios_cargo(request):
    exercicios = database.listar_exercicios_cargo()

    return render(
        request,
        'associacao/listar_exercicios_cargo.html',
        {'exercicios': exercicios}
    )