from django.urls import path
from . import views

urlpatterns = [
    path(
        'mandatos/',
        views.listar_mandatos,
        name='listar_mandatos'
    ),
    path(
        'mandatos/novo/',
        views.registar_mandato,
        name='registar_mandato'
    ),

    path(
        'exercicios-cargo/',
        views.listar_exercicios_cargo,
        name='listar_exercicios_cargo'
    ),
    path(
        'exercicios-cargo/novo/',
        views.registar_exercicio_cargo,
        name='registar_exercicio_cargo'
    ),
]